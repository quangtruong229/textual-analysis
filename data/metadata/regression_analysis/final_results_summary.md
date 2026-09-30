# Final Results Summary

Source: event_study_final/event_study_summary.csv + regression_analysis/regression_results.csv

Primary regression inference uses HC3 standard errors. C1-C3 hypothesis rows are restricted to LM positive/negative tone variables.

| analysis | specification | window | variable | estimate | se_hc3 | p_two_sided | p_one_sided | p_cluster_two_sided | N | firms | secondary_p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Event Study | Market Model | [-1,+1] | CAAR | 0.004029 | 0.000954 | 0.000024 |  |  | 969 |  | 0.042985 |
| Regression | C1 | [-1,+1] | lm_negative_prop | 0.111410 | 0.198364 | 0.574487 | 0.712756 | 0.604759 | 969 | 100.0 |  |
| Regression | C1 | [-1,+1] | lm_positive_prop | -1.410381 | 0.509292 | 0.005725 | 0.997137 | 0.027209 | 969 | 100.0 |  |
| Regression | C2 | [-1,+1] | lm_negative_prop | 0.075636 | 0.204840 | 0.712029 | 0.643985 | 0.721379 | 955 | 99.0 |  |
| Regression | C2 | [-1,+1] | lm_positive_prop | -1.363261 | 0.519204 | 0.008787 | 0.995607 | 0.057600 | 955 | 99.0 |  |
| Regression | C3 | [-1,+1] | lm_negative_prop | 0.129648 | 0.205792 | 0.528849 | 0.735576 | 0.550272 | 955 | 99.0 |  |
| Regression | C3 | [-1,+1] | lm_positive_prop | -1.386300 | 0.527022 | 0.008666 | 0.995667 | 0.056189 | 955 | 99.0 |  |
| Regression | C4 Proportional | [-1,+1] | harvard_net_prop | -0.625634 | 0.259725 | 0.016190 |  | 0.013590 | 969 | 100.0 |  |
| Regression | C4 Proportional | [-1,+1] | lm_net_prop | -0.085735 | 0.250208 | 0.731934 |  | 0.776720 | 969 | 100.0 |  |
| Regression | C4 TFIDF | [-1,+1] | harvard_net_tfidf | -0.000107 | 0.000394 | 0.786158 |  | 0.795195 | 969 | 100.0 |  |
| Regression | C4 TFIDF | [-1,+1] | lm_net_tfidf | -0.000216 | 0.000162 | 0.183612 |  | 0.234991 | 969 | 100.0 |  |
| Event Study | Market Model | [0,+3] | CAAR | 0.003446 | 0.001101 | 0.001754 |  |  | 969 |  | 0.077253 |
| Regression | C1 | [0,+3] | lm_negative_prop | 0.071841 | 0.195013 | 0.712663 | 0.643669 | 0.675533 | 969 | 100.0 |  |
| Regression | C1 | [0,+3] | lm_positive_prop | -0.491827 | 0.480720 | 0.306514 | 0.846743 | 0.193032 | 969 | 100.0 |  |
| Regression | C2 | [0,+3] | lm_negative_prop | -0.002621 | 0.193262 | 0.989184 | 0.494592 | 0.987492 | 955 | 99.0 |  |
| Regression | C2 | [0,+3] | lm_positive_prop | -0.466527 | 0.494368 | 0.345571 | 0.827214 | 0.319576 | 955 | 99.0 |  |
| Regression | C3 | [0,+3] | lm_negative_prop | 0.015665 | 0.194871 | 0.935948 | 0.532026 | 0.926082 | 955 | 99.0 |  |
| Regression | C3 | [0,+3] | lm_positive_prop | -0.469311 | 0.499921 | 0.348088 | 0.825956 | 0.320035 | 955 | 99.0 |  |
| Regression | C4 Proportional | [0,+3] | harvard_net_prop | -0.404903 | 0.231715 | 0.080883 |  | 0.057338 | 969 | 100.0 |  |
| Regression | C4 Proportional | [0,+3] | lm_net_prop | 0.021094 | 0.241846 | 0.930513 |  | 0.919727 | 969 | 100.0 |  |
| Regression | C4 TFIDF | [0,+3] | harvard_net_tfidf | -0.000243 | 0.000374 | 0.515770 |  | 0.539348 | 969 | 100.0 |  |
| Regression | C4 TFIDF | [0,+3] | lm_net_tfidf | -0.000106 | 0.000155 | 0.493233 |  | 0.439194 | 969 | 100.0 |  |
| Event Study | Market Model | [-3,+3] | CAAR | 0.005934 | 0.001457 | 0.000046 |  |  | 969 |  | 0.319316 |
| Regression | C1 | [-3,+3] | lm_negative_prop | 0.171275 | 0.281820 | 0.543499 | 0.728250 | 0.450303 | 969 | 100.0 |  |
| Regression | C1 | [-3,+3] | lm_positive_prop | -2.254072 | 0.668565 | 0.000777 | 0.999611 | 0.005599 | 969 | 100.0 |  |
| Regression | C2 | [-3,+3] | lm_negative_prop | 0.184460 | 0.278032 | 0.507204 | 0.746398 | 0.433141 | 955 | 99.0 |  |
| Regression | C2 | [-3,+3] | lm_positive_prop | -2.135872 | 0.685855 | 0.001900 | 0.999050 | 0.020063 | 955 | 99.0 |  |
| Regression | C3 | [-3,+3] | lm_negative_prop | 0.269544 | 0.276258 | 0.329464 | 0.835268 | 0.272205 | 955 | 99.0 |  |
| Regression | C3 | [-3,+3] | lm_positive_prop | -2.183771 | 0.685914 | 0.001501 | 0.999249 | 0.016814 | 955 | 99.0 |  |
| Regression | C4 Proportional | [-3,+3] | harvard_net_prop | -1.044856 | 0.362609 | 0.004046 |  | 0.004461 | 969 | 100.0 |  |
| Regression | C4 Proportional | [-3,+3] | lm_net_prop | -0.111835 | 0.329545 | 0.734410 |  | 0.761165 | 969 | 100.0 |  |
| Regression | C4 TFIDF | [-3,+3] | harvard_net_tfidf | -0.000235 | 0.000540 | 0.663178 |  | 0.656272 | 969 | 100.0 |  |
| Regression | C4 TFIDF | [-3,+3] | lm_net_tfidf | -0.000506 | 0.000253 | 0.045826 |  | 0.057622 | 969 | 100.0 |  |
| Event Study | Market Model | [-5,+5] | CAAR | 0.007463 | 0.001827 | 0.000044 |  |  | 969 |  | 0.042985 |
| Regression | C1 | [-5,+5] | lm_negative_prop | 0.209986 | 0.378366 | 0.579037 | 0.710482 | 0.497384 | 969 | 100.0 |  |
| Regression | C1 | [-5,+5] | lm_positive_prop | -2.051655 | 0.844167 | 0.015264 | 0.992368 | 0.019397 | 969 | 100.0 |  |
| Regression | C2 | [-5,+5] | lm_negative_prop | 0.099285 | 0.373372 | 0.790363 | 0.604819 | 0.759431 | 955 | 99.0 |  |
| Regression | C2 | [-5,+5] | lm_positive_prop | -1.926484 | 0.855985 | 0.024639 | 0.987681 | 0.056557 | 955 | 99.0 |  |
| Regression | C3 | [-5,+5] | lm_negative_prop | 0.175560 | 0.375702 | 0.640404 | 0.679798 | 0.603971 | 955 | 99.0 |  |
| Regression | C3 | [-5,+5] | lm_positive_prop | -1.957682 | 0.858034 | 0.022735 | 0.988633 | 0.052397 | 955 | 99.0 |  |
| Regression | C4 Proportional | [-5,+5] | harvard_net_prop | -0.757723 | 0.444769 | 0.088771 |  | 0.046126 | 969 | 100.0 |  |
| Regression | C4 Proportional | [-5,+5] | lm_net_prop | -0.231920 | 0.407437 | 0.569342 |  | 0.582920 | 969 | 100.0 |  |
| Regression | C4 TFIDF | [-5,+5] | harvard_net_tfidf | -0.000725 | 0.000678 | 0.284972 |  | 0.259221 | 969 | 100.0 |  |
| Regression | C4 TFIDF | [-5,+5] | lm_net_tfidf | -0.000796 | 0.000329 | 0.015739 |  | 0.011263 | 969 | 100.0 |  |

## Model definitions

- C1: Score only.

- C2: Score + Size + BM + Volatility + Turnover.

- C3: LM Positive + LM Negative + Size + BM + Volatility + Turnover.

- C4: LM vs Harvard, estimated separately for proportional and TF-IDF scores.

- EADRet and Accruals are excluded from the primary specification in the current phase.
