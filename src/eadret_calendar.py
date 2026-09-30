from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import exchange_calendars as xcals


XNYS = xcals.get_calendar("XNYS")


@dataclass(frozen=True)
class EventSessionResolution:
    acceptance_utc: pd.Timestamp
    acceptance_et: pd.Timestamp
    event_session: pd.Timestamp
    session_close_utc: pd.Timestamp
    rule: str


def _as_utc(ts) -> pd.Timestamp:
    """Parse timestamp and normalize to timezone-aware UTC."""
    out = pd.Timestamp(ts)
    if out.tzinfo is None:
        out = out.tz_localize("UTC")
    else:
        out = out.tz_convert("UTC")
    return out


def resolve_event_session(
    acceptance_ts,
    calendar=XNYS,
) -> EventSessionResolution:
    """
    Map an SEC acceptance timestamp to the economically relevant XNYS session.

    Rules
    -----
    1. If acceptance local date is not an XNYS session (weekend/holiday),
       use the next XNYS session.
    2. If acceptance occurs on an XNYS session and is at/before that
       session's actual close, use the same session.
    3. If acceptance is after the actual close, use the next XNYS session.

    This intentionally treats pre-market acceptance as belonging to the
    same trading session, consistent with the project's current EADRet logic.
    """
    acceptance_utc = _as_utc(acceptance_ts)
    acceptance_et = acceptance_utc.tz_convert("America/New_York")
    local_date = acceptance_et.date()

    candidate = calendar.date_to_session(local_date, direction="next")
    candidate_close = calendar.session_close(candidate)

    # If local_date itself is not a session, date_to_session(..., "next")
    # returns a later session. In that case event session is necessarily that
    # next session.
    if candidate.date() != local_date:
        return EventSessionResolution(
            acceptance_utc=acceptance_utc,
            acceptance_et=acceptance_et,
            event_session=candidate,
            session_close_utc=candidate_close,
            rule="non_trading_day_to_next_session",
        )

    if acceptance_utc <= candidate_close:
        return EventSessionResolution(
            acceptance_utc=acceptance_utc,
            acceptance_et=acceptance_et,
            event_session=candidate,
            session_close_utc=candidate_close,
            rule="same_session_before_or_at_actual_close",
        )

    next_session = calendar.next_session(candidate)
    return EventSessionResolution(
        acceptance_utc=acceptance_utc,
        acceptance_et=acceptance_et,
        event_session=next_session,
        session_close_utc=candidate_close,
        rule="after_actual_close_to_next_session",
    )


def event_sessions(
    event_session,
    event_start: int = 0,
    event_end: int = 2,
    calendar=XNYS,
) -> pd.DatetimeIndex:
    """
    Return XNYS sessions for configurable event window [event_start, event_end].

    Examples
    --------
    [0, +2]  -> event session + next 2 trading sessions
    [-1, +1] -> previous session + event session + next session
    """
    if event_start > event_end:
        raise ValueError("event_start must be <= event_end")

    base = pd.Timestamp(event_session)

    # sessions_window(session, count) in exchange_calendars 4.13.1
    # returns exactly `count` sessions. Negative count walks backwards.
    if event_start < 0:
        # Example: event_start=-1 -> [previous_session, base], take first.
        start = calendar.sessions_window(base, event_start - 1)[0]
    elif event_start > 0:
        # Example: event_start=1 -> [base, next_session], take last.
        start = calendar.sessions_window(base, event_start + 1)[-1]
    else:
        start = base

    count = event_end - event_start + 1
    return calendar.sessions_window(start, count)


def buy_and_hold_return(returns: Iterable[float]) -> float:
    """Compound daily simple returns."""
    s = pd.Series(list(returns), dtype="float64")
    if s.isna().any():
        raise ValueError("Missing return inside event window")
    return float((1.0 + s).prod() - 1.0)


def calculate_eadret(
    stock_returns: Iterable[float],
    market_returns: Iterable[float],
) -> tuple[float, float, float]:
    """
    Return (stock_bhar, market_bhar, eadret)
    where EADRet = stock BHAR - market BHAR.
    """
    stock_bhar = buy_and_hold_return(stock_returns)
    market_bhar = buy_and_hold_return(market_returns)
    return stock_bhar, market_bhar, stock_bhar - market_bhar


def select_latest_earnings_8k_before_10k(
    submissions: pd.DataFrame,
    tenk_acceptance_ts,
) -> pd.Series:
    """
    Select the latest earnings-announcement 8-K before the 10-K acceptance.

    Expected columns:
      - form
      - items
      - acceptanceDateTime
      - filingDate
      - accessionNumber

    Filtering:
      - form == '8-K'
      - Item 2.02 present in SEC 'items'
      - acceptance timestamp strictly earlier than 10-K acceptance timestamp

    Using acceptance timestamps prevents a same-day 8-K filed after the 10-K
    from being incorrectly selected merely because filingDate is equal.
    """
    required = {
        "form", "items", "acceptanceDateTime",
        "filingDate", "accessionNumber",
    }
    missing = required.difference(submissions.columns)
    if missing:
        raise KeyError(f"Missing submission columns: {sorted(missing)}")

    tenk_accept = _as_utc(tenk_acceptance_ts)

    x = submissions.copy()
    x["acceptance_utc"] = pd.to_datetime(
        x["acceptanceDateTime"], utc=True, errors="coerce"
    )

    is_8k = x["form"].astype(str).str.upper().eq("8-K")
    has_202 = (
        x["items"]
        .fillna("")
        .astype(str)
        .str.split(",")
        .apply(lambda vals: any(v.strip() == "2.02" for v in vals))
    )
    before_10k = x["acceptance_utc"].notna() & (x["acceptance_utc"] < tenk_accept)

    candidates = x.loc[is_8k & has_202 & before_10k].sort_values(
        ["acceptance_utc", "accessionNumber"]
    )

    if candidates.empty:
        raise LookupError("No prior 8-K Item 2.02 found before 10-K acceptance")

    return candidates.iloc[-1]
