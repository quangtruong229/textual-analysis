"""Estimate leave-one-filing-year-out LM Word Power from verified Item 7 terms.

The positive list uses J&W Eq. 6 OLS when identified. The negative list is
larger relative to this sample, so its Eq. 6 first stage uses ridge with a
penalty chosen only on training years. Both lists use Eq. 7 weights and Eq. 4
scores; no held-out filing year's CAR enters its own weights.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy import linalg, sparse
from scipy.sparse.linalg import LinearOperator, lsqr

from optional_robustness import fit_model

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_outputs/word_power"
KEY = ["ticker", "filing_date"]
SIX = ["size", "bm", "volatility", "turnover", "eadret", "accruals"]
WINDOWS = ["car_m1_p1", "car_0_p3", "car_m3_p3", "car_m5_p5"]
MIN_TRAIN_DOCUMENTS = 5
RIDGE_ALPHAS = (1.0, 10.0, 100.0, 1000.0, 10000.0, 100000.0, 1000000.0)


def normalized_accession(value: object) -> str:
    return str(value).replace("-", "").strip()


def load_inputs() -> tuple[pd.DataFrame, dict[str, sparse.csr_matrix], dict[str, list[str]]]:
    tone = pd.read_csv(ROOT / "data/metadata/tone_method_item7.csv",
                       dtype={"accession_number": str})
    event = pd.read_csv(ROOT / "analysis_outputs/regression/regression_sample.csv")
    if tone.duplicated(KEY).any() or event.duplicated(KEY).any():
        raise ValueError("Duplicate tone or event filing key")
    panel = tone[[*KEY, "accession_number", "lm_total_words",
                  "lm_positive_prop", "lm_negative_prop"]].copy()
    panel = panel.sort_values(KEY).reset_index(drop=True)
    panel["filing_year"] = panel.filing_date.str[:4].astype(int)
    panel = panel.merge(event[[*KEY, *WINDOWS]], on=KEY, how="left", validate="one_to_one")
    if panel.lm_total_words.isna().any() or panel.lm_total_words.le(0).any():
        raise ValueError("Item 7 token counts must be positive")
    if panel.car_0_p3.notna().sum() != 969:
        raise ValueError("Unexpected event-study sample; rebuild event outputs first")

    terms = pd.read_csv(ROOT / "data/item7_corpus/item7_lm_sentiment_counts.csv.gz",
                        dtype={"accession_number": str})
    if not terms.category.isin(["positive", "negative"]).all():
        raise ValueError("Unexpected LM category in word corpus")
    accession_index = {normalized_accession(a): i for i, a in enumerate(panel.accession_number)}
    if len(accession_index) != len(panel):
        raise ValueError("Duplicate accession in tone panel")
    terms["row"] = terms.accession_number.map(lambda a: accession_index.get(normalized_accession(a)))
    if terms.row.isna().any() or terms["count"].isna().any() or terms["count"].le(0).any():
        raise ValueError("Term table has unknown accession or invalid frequency")
    indexed = panel.loc[terms.row.astype(int), [*KEY]].reset_index(drop=True)
    if not indexed.ticker.eq(terms.ticker.reset_index(drop=True)).all() or not indexed.filing_date.eq(
            terms.filing_date.reset_index(drop=True)).all():
        raise ValueError("Term accession does not match ticker and filing date")

    matrices: dict[str, sparse.csr_matrix] = {}
    lexicons: dict[str, list[str]] = {}
    totals = panel.lm_total_words.to_numpy(dtype=float)
    for category in ("positive", "negative"):
        group = terms.loc[terms.category.eq(category)]
        lexicon = sorted(group.term.unique().tolist())
        col_index = {term: i for i, term in enumerate(lexicon)}
        rows = group.row.to_numpy(dtype=int)
        cols = group.term.map(col_index).to_numpy(dtype=int)
        values = group["count"].to_numpy(dtype=float) / totals[rows]
        matrix = sparse.coo_matrix((values, (rows, cols)), shape=(len(panel), len(lexicon))).tocsr()
        matrix.sum_duplicates()
        matrices[category] = matrix
        lexicons[category] = lexicon
        reconstructed = np.asarray(matrix.sum(axis=1)).ravel()
        expected = panel[f"lm_{category}_prop"].to_numpy(dtype=float)
        if not np.allclose(reconstructed, expected, rtol=1e-10, atol=1e-12):
            raise ValueError(f"Per-term {category} counts do not rebuild supplied tone")
    return panel, matrices, lexicons


def ridge_fit(matrix: sparse.csr_matrix, target: np.ndarray,
              alpha: float) -> tuple[np.ndarray, float, int]:
    """Ridge on variance-scaled columns, with an unpenalized intercept."""
    means = np.asarray(matrix.mean(axis=0)).ravel()
    second = np.asarray(matrix.power(2).mean(axis=0)).ravel()
    scales = np.sqrt(np.maximum(second - means**2, 0.0))
    usable = scales > 1e-12
    safe_scales = np.where(usable, scales, 1.0)
    scaled = matrix.multiply(1.0 / safe_scales).tocsr()
    scaled_means = means / safe_scales
    n_rows, n_cols = scaled.shape

    def matvec(beta: np.ndarray) -> np.ndarray:
        return np.asarray(scaled @ beta).ravel() - np.dot(scaled_means, beta)

    def rmatvec(residual: np.ndarray) -> np.ndarray:
        return np.asarray(scaled.T @ residual).ravel() - scaled_means * residual.sum()

    operator = LinearOperator((n_rows, n_cols), matvec=matvec, rmatvec=rmatvec, dtype=float)
    answer = lsqr(operator, target - target.mean(), damp=np.sqrt(alpha),
                  atol=1e-8, btol=1e-8, iter_lim=1000)
    if answer[1] not in (1, 2) or not np.isfinite(answer[0]).all():
        raise ValueError(f"Ridge solver did not converge: stop={answer[1]}")
    coefficients = answer[0] / safe_scales
    coefficients[~usable] = 0.0
    intercept = float(target.mean() - np.dot(means, coefficients))
    return coefficients, intercept, int(answer[2])


def choose_alpha(matrix: sparse.csr_matrix, target: np.ndarray,
                 filing_years: np.ndarray) -> tuple[float, dict[str, float]]:
    years = sorted(np.unique(filing_years).tolist())
    if len(years) < 6:
        raise ValueError("Need multiple training years for inner validation")
    assignment = {year: i % 3 for i, year in enumerate(years)}
    groups = np.array([assignment[year] for year in filing_years])
    losses = {}
    for alpha in RIDGE_ALPHAS:
        squared_error = 0.0
        n_valid = 0
        for fold in range(3):
            train = groups != fold
            valid = ~train
            coefficients, _, _ = ridge_fit(matrix[train], target[train], alpha)
            spread = float(np.std(coefficients, ddof=0))
            if not np.isfinite(spread) or spread <= 0:
                raise ValueError("Degenerate inner-validation Word Power weights")
            weights = (coefficients - coefficients.mean()) / spread
            train_score = np.asarray(matrix[train] @ weights).ravel()
            valid_score = np.asarray(matrix[valid] @ weights).ravel()
            score_var = float(np.var(train_score))
            if score_var <= 0:
                raise ValueError("Degenerate inner-validation Word Power score")
            slope = float(np.mean((train_score - train_score.mean())
                                  * (target[train] - target[train].mean())) / score_var)
            intercept = float(target[train].mean() - slope * train_score.mean())
            predicted = intercept + slope * valid_score
            squared_error += float(np.square(target[valid] - predicted).sum())
            n_valid += int(valid.sum())
        losses[str(alpha)] = squared_error / n_valid
    chosen = min(RIDGE_ALPHAS, key=lambda alpha: (losses[str(alpha)], alpha))
    return chosen, losses


def fit_weights(matrix: sparse.csr_matrix, target: np.ndarray,
                filing_years: np.ndarray, category: str,
                forced_alpha: float | None = None) -> tuple[np.ndarray, dict]:
    frequency = np.asarray((matrix != 0).sum(axis=0)).ravel()
    active = frequency >= MIN_TRAIN_DOCUMENTS
    if active.sum() < 10:
        raise ValueError(f"Too few active {category} terms")
    train_matrix = matrix[:, active].tocsr()
    if category == "positive":
        dense = train_matrix.toarray()
        centered = dense - dense.mean(axis=0)
        coefficients, _, rank, _ = linalg.lstsq(
            centered, target - target.mean(), lapack_driver="gelsy")
        if rank != active.sum():
            raise ValueError(f"Positive Word Power OLS not identified: rank {rank}/{active.sum()}")
        estimator = "OLS_Eq6"
        alpha = 0.0
        inner_losses: dict[str, float] = {}
        iterations = 0
    else:
        if forced_alpha is None:
            alpha, inner_losses = choose_alpha(train_matrix, target, filing_years)
        else:
            alpha, inner_losses = forced_alpha, {}
        coefficients, _, iterations = ridge_fit(train_matrix, target, alpha)
        rank = None
        estimator = "ridge_Eq6_small_sample_adaptation"
    spread = float(np.std(coefficients, ddof=0))
    if not np.isfinite(spread) or spread <= 0:
        raise ValueError(f"Degenerate {category} word weights")
    weights = np.zeros(matrix.shape[1], dtype=float)
    weights[active] = (coefficients - coefficients.mean()) / spread
    full_coefficients = np.zeros(matrix.shape[1], dtype=float)
    full_coefficients[active] = coefficients
    diagnostic = {
        "category": category, "estimator": estimator, "alpha": alpha,
        "rank": int(rank) if rank is not None else None,
        "iterations": iterations, "training_documents": len(target),
        "active_terms": int(active.sum()), "available_terms": matrix.shape[1],
        "inner_year_cv_mse": inner_losses,
        "active_mask": active, "coefficients": full_coefficients,
        "training_document_frequency": frequency,
    }
    return weights, diagnostic


def make_scores(panel: pd.DataFrame, matrices: dict[str, sparse.csr_matrix],
                lexicons: dict[str, list[str]]) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    y = panel.car_0_p3.to_numpy(dtype=float)
    years = panel.filing_year.to_numpy(dtype=int)
    result = panel[[*KEY, "accession_number", "filing_year", "lm_total_words"]].copy()
    for category in ("positive", "negative"):
        result[f"lm_{category}_wp"] = np.nan
    weight_rows = []
    diagnostics = []
    for held_year in sorted(np.unique(years)):
        train = (years != held_year) & np.isfinite(y)
        test = years == held_year
        if np.any(years[train] == held_year):
            raise AssertionError("Held-out year leaked into Word Power training")
        for category in ("positive", "negative"):
            matrix = matrices[category]
            weights, diagnostic = fit_weights(matrix[train], y[train], years[train], category)
            score = np.asarray(matrix[test] @ weights).ravel()
            result.loc[test, f"lm_{category}_wp"] = score
            diagnostic["held_out_year"] = int(held_year)
            diagnostic["scored_documents"] = int(test.sum())
            diagnostic["train_years"] = [int(year) for year in sorted(np.unique(years[train]))]
            active = diagnostic.pop("active_mask")
            coefficients = diagnostic.pop("coefficients")
            frequency = diagnostic.pop("training_document_frequency")
            for term, weight, coefficient, df in zip(lexicons[category], weights, coefficients, frequency):
                if df >= MIN_TRAIN_DOCUMENTS:
                    weight_rows.append({"held_out_year": int(held_year), "category": category,
                                        "term": term, "weight": float(weight),
                                        "coefficient_eq6": float(coefficient),
                                        "training_document_frequency": int(df),
                                        "estimator": diagnostic["estimator"], "alpha": diagnostic["alpha"]})
            diagnostics.append(diagnostic)
        print(f"Estimated Word Power weights outside filing year {held_year}", flush=True)
    if result[["lm_positive_wp", "lm_negative_wp"]].isna().any().any():
        raise ValueError("Missing out-of-year Word Power score")
    return result, pd.DataFrame(weight_rows), diagnostics


def run_regressions(scores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    event = pd.read_csv(ROOT / "analysis_outputs/regression/regression_sample.csv")
    full = pd.read_csv(ROOT / "analysis_outputs/c2_full6_sample.csv",
                       dtype={"accession_number": str})
    if scores.duplicated(KEY).any() or full.duplicated(KEY).any():
        raise ValueError("Duplicate filing key in Word Power or six-control sample")
    sample = event.merge(scores[[*KEY, "accession_number", "filing_year",
                                 "lm_positive_wp", "lm_negative_wp"]],
                         on=KEY, validate="one_to_one")
    full = full.merge(scores[[*KEY, "lm_positive_wp", "lm_negative_wp"]],
                      on=KEY, validate="one_to_one")
    if len(sample) != 969 or len(full) != 481:
        raise ValueError("Word Power regression sample no longer matches audited cohort")
    models = [
        (sample, ["lm_positive_wp"], "C1_H1_WP_positive"),
        (sample, ["lm_negative_wp"], "C1_H2_WP_negative"),
        (sample, ["lm_positive_prop"], "C1_positive_proportion_same_sample"),
        (sample, ["lm_negative_prop"], "C1_negative_proportion_same_sample"),
        (sample, ["lm_positive_wp", "lm_negative_wp"], "C3_WP_posneg"),
        (full, ["lm_positive_wp", *SIX], "C2_H1_WP_positive_six_controls"),
        (full, ["lm_negative_wp", *SIX], "C2_H2_WP_negative_six_controls"),
        (full, ["lm_positive_wp", "lm_negative_wp", *SIX], "C3_WP_posneg_six_controls"),
        (full, ["lm_positive_prop", *SIX], "C2_positive_proportion_same_sample"),
        (full, ["lm_negative_prop", *SIX], "C2_negative_proportion_same_sample"),
    ]
    rows = []
    for frame, predictors, name in models:
        for dependent in WINDOWS:
            rows.extend(fit_model(frame, dependent, predictors, name))
    results = pd.DataFrame(rows)
    mask = results.term.isin(["lm_positive_wp", "lm_negative_wp"])
    positive_direction = results.loc[mask, "coefficient"].gt(0)
    results.loc[mask, "hypothesis_direction"] = ">0"
    results.loc[mask, "p_hc3_one_sided"] = np.where(
        positive_direction,
        results.loc[mask, "p_hc3_two_sided"] / 2,
        1 - results.loc[mask, "p_hc3_two_sided"] / 2,
    )
    results.loc[mask, "p_cluster_one_sided"] = np.where(
        positive_direction,
        results.loc[mask, "p_cluster_two_sided"] / 2,
        1 - results.loc[mask, "p_cluster_two_sided"] / 2,
    )
    return results, full


def ridge_sensitivity(panel: pd.DataFrame,
                      negative_matrix: sparse.csr_matrix) -> pd.DataFrame:
    event = pd.read_csv(ROOT / "analysis_outputs/regression/regression_sample.csv")
    full = pd.read_csv(ROOT / "analysis_outputs/c2_full6_sample.csv")
    years = panel.filing_year.to_numpy(dtype=int)
    target = panel.car_0_p3.to_numpy(dtype=float)
    records = []
    for alpha in (1000.0, 10000.0, 100000.0, 1000000.0):
        out_of_year = np.full(len(panel), np.nan)
        for held_year in sorted(np.unique(years)):
            train = (years != held_year) & np.isfinite(target)
            test = years == held_year
            weights, _ = fit_weights(negative_matrix[train], target[train],
                                     years[train], "negative", forced_alpha=alpha)
            out_of_year[test] = np.asarray(negative_matrix[test] @ weights).ravel()
        score_frame = panel[KEY].copy()
        score_frame["score"] = out_of_year
        for name, frame, predictors in (
            ("C1", event, ["score"]),
            ("C2_six_controls", full, ["score", *SIX]),
        ):
            sample = frame.merge(score_frame, on=KEY, validate="one_to_one")
            rows = fit_model(sample, "car_0_p3", predictors, f"H2_WP_{name}_ridge_sensitivity")
            coefficient = next(row for row in rows if row["term"] == "score")
            records.append({
                "alpha": alpha, "model": name, "n": len(sample),
                "coefficient": coefficient["coefficient"],
                "coefficient_per_score_sd": coefficient["coefficient"] * sample.score.std(ddof=1),
                "p_hc3_two_sided": coefficient["p_hc3_two_sided"],
                "p_cluster_two_sided": coefficient["p_cluster_two_sided"],
            })
    return pd.DataFrame(records)


def write_report(results: pd.DataFrame, scores: pd.DataFrame,
                 full: pd.DataFrame, diagnostics: list[dict],
                 sensitivity: pd.DataFrame) -> None:
    event_keys = pd.read_csv(ROOT / "analysis_outputs/regression/regression_sample.csv")[KEY]
    event_scores = event_keys.merge(scores, on=KEY, validate="one_to_one")
    def coefficient(model: str, term: str) -> pd.Series:
        rows = results.loc[
            results.model.eq(model) & results.dependent_variable.eq("car_0_p3")
            & results.term.eq(term)]
        if len(rows) != 1:
            raise ValueError(f"Missing primary Word Power result: {model}/{term}")
        return rows.iloc[0]

    rows = []
    for model, term, label, sample in (
        ("C1_H1_WP_positive", "lm_positive_wp", "H1, C1", event_scores),
        ("C1_H2_WP_negative", "lm_negative_wp", "H2, C1", event_scores),
        ("C2_H1_WP_positive_six_controls", "lm_positive_wp", "H1, C2 đủ 6 controls", full),
        ("C2_H2_WP_negative_six_controls", "lm_negative_wp", "H2, C2 đủ 6 controls", full),
    ):
        row = coefficient(model, term)
        effect_pp = row.coefficient * sample[term].std(ddof=1) * 100
        rows.append(f"| {label} | {int(row.n)} | {row.coefficient:.4f} | {effect_pp:+.3f} | "
                    f"{row.p_hc3_one_sided:.4f} | {row.p_cluster_one_sided:.4f} |")
    sensitivity_rows = []
    for row in sensitivity.itertuples():
        sensitivity_rows.append(
            f"| {int(row.alpha):,} | {row.model} | {row.coefficient_per_score_sd * 100:+.3f} | "
            f"{row.p_hc3_two_sided:.4f} | {row.p_cluster_two_sided:.4f} |")
    positive = [d for d in diagnostics if d["category"] == "positive"]
    negative = [d for d in diagnostics if d["category"] == "negative"]
    upper = sum(d["alpha"] == max(RIDGE_ALPHAS) for d in negative)
    report = f"""# Word Power và kiểm định H1/H2

Đầu vào là 971 Item 7 đã tải từ SEC, bảng tần suất **sau quy tắc phủ định A1** tại `data/item7_corpus/item7_lm_sentiment_counts.csv.gz`, và CAR mô hình thị trường. Với mỗi năm nộp, trọng số từ được ước lượng từ **mọi năm khác năm đó**; năm được chấm điểm không tham gia bước ước lượng trọng số của chính mình. Biến mục tiêu bước ước lượng là CAR `[0,+3]`. Điểm bằng tổng `w_j × F_ij / a_i`, với `a_i` là số token Item 7, rồi chuẩn hóa hệ số từ theo Eq. 7 của [Jegadeesh–Wu (2013)](https://repository.upenn.edu/server/api/core/bitstreams/caf9d0c9-0de5-475a-ac72-f6e4ad3bfce5/content).

Danh sách tích cực dùng OLS Eq. 6, chỉ giữ từ xuất hiện trong ít nhất {MIN_TRAIN_DOCUMENTS} văn bản huấn luyện. Ma trận có đủ hạng ở cả 10 lần ước lượng ({min(d['active_terms'] for d in positive)}–{max(d['active_terms'] for d in positive)} từ). Danh sách tiêu cực có nhiều từ so với cỡ mẫu; để giảm hệ số bất ổn, bước Eq. 6 dùng **ridge**, chọn penalty bằng kiểm tra chéo theo năm trong tập huấn luyện, sau khi chuẩn hóa Score và hiệu chỉnh Eq. 8. Đây là **điều chỉnh cho mẫu nhỏ**, không phải tái lập nguyên xi ước lượng OLS của bài gốc. {upper}/10 lần chọn mức phạt cao nhất của lưới, cho thấy trọng số tiêu cực thiếu ổn định.

Điểm Word Power của **cả hai danh sách** càng cao thì ngôn từ càng gắn với CAR cao trong tập huấn luyện. Do đó dấu kỳ vọng cho H2 Word Power là **dương**; dấu âm chỉ áp dụng cho tỷ lệ từ tiêu cực chưa điều chỉnh trọng số. Các mô hình dưới đây dùng CAR `[0,+3]`; p một phía kiểm tra hệ số `> 0`, đúng chiều giả thuyết. Cột hiệu ứng là thay đổi CAR tính bằng **điểm phần trăm** khi Score tăng một độ lệch chuẩn trong đúng mẫu của mô hình.

| Mô hình | N | Hệ số/1 đơn vị Score | CAR điểm %/1 SD | p HC3 một phía | p cụm công ty một phía |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

Các hệ số H1/H2 trong đặc tả chính không đạt mức 5% theo chiều kỳ vọng. Bảng `regression_results.csv` còn chứa C3 dùng đồng thời hai Score, ba cửa sổ CAR còn lại và mô hình tone tỷ lệ trên cùng mẫu để đối chiếu. Mẫu sáu controls chỉ dùng 481 hồ sơ của 71 công ty có Accruals `PASS` và các biến còn lại hợp lệ.

## Độ nhạy của danh sách tiêu cực

Đây là hồi quy `[0,+3]` khi cố định penalty ở các mức khác nhau; p trong bảng là **hai phía**. Hiệu ứng cùng đơn vị điểm phần trăm CAR cho một độ lệch chuẩn Score.

| Ridge alpha | Mô hình | CAR điểm %/1 SD | p HC3 hai phía | p cụm hai phía |
| ---: | --- | ---: | ---: | ---: |
{chr(10).join(sensitivity_rows)}

`qa.json` ghi số từ, bậc hạng, số hồ sơ huấn luyện và penalty của từng năm; `annual_weights.csv.gz` lưu trọng số từng từ. Các p-value HC3 và cụm công ty **điều kiện trên Score đã ước lượng**; chúng chưa phản ánh đầy đủ bất định ở bước tạo trọng số. Mẫu 100 công ty/10 năm, cách đo CAR theo mô hình thị trường, lọc từ ít xuất hiện và ridge cho từ tiêu cực đều khác bài J&W. Kết quả mô tả liên hệ, không chứng minh quan hệ nhân quả hoặc khả năng giao dịch sinh lời.
"""
    (OUT / "RESULTS.md").write_text(report, encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    panel, matrices, lexicons = load_inputs()
    scores, weights, diagnostics = make_scores(panel, matrices, lexicons)
    scores.to_csv(OUT / "scores.csv", index=False)
    weights.to_csv(OUT / "annual_weights.csv.gz", index=False, compression="gzip")
    results, full = run_regressions(scores)
    results.to_csv(OUT / "regression_results.csv", index=False)
    full.to_csv(OUT / "six_control_sample.csv", index=False)
    sensitivity = ridge_sensitivity(panel, matrices["negative"])
    sensitivity.to_csv(OUT / "ridge_sensitivity.csv", index=False)
    report = {
        "method": "J&W Eq. 4/6/7 adapted to a smaller 10-K sample",
        "target_for_weights": "market-model CAR [0,+3]",
        "leave_out_unit": "filing_year",
        "positive_first_stage": "OLS Eq. 6 if full rank",
        "negative_first_stage": "ridge Eq. 6 with alpha selected by inner training-year CV",
        "minimum_training_document_frequency": MIN_TRAIN_DOCUMENTS,
        "positive_weight_sign": "higher score means words associated with higher CAR",
        "negative_weight_sign": "higher score also means words associated with higher CAR; H2 WP expects beta > 0",
        "inference_limit": "HC3 and firm-cluster p-values condition on generated cross-fitted scores",
        "scored_filings": len(scores), "regression_filings": 969,
        "six_control_filings": len(full),
        "folds": diagnostics,
    }
    (OUT / "qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(results, scores, full, diagnostics, sensitivity)
    primary = results.loc[
        results.dependent_variable.eq("car_0_p3")
        & results.term.isin(["lm_positive_wp", "lm_negative_wp"]),
        ["model", "term", "n", "n_firms", "coefficient", "p_hc3_two_sided",
         "p_hc3_one_sided", "p_cluster_two_sided", "p_cluster_one_sided"],
    ]
    print(primary.to_string(index=False))


if __name__ == "__main__":
    main()
