import pandas as pd

from eadret_calendar import (
    XNYS,
    calculate_eadret,
    event_sessions,
    resolve_event_session,
)


def test_aapl_2025_after_close():
    # Handoff: 2025-10-30T20:30:35Z = 16:30:35 ET -> next session.
    r = resolve_event_session("2025-10-30T20:30:35Z")
    assert str(r.event_session.date()) == "2025-10-31"
    assert r.rule == "after_actual_close_to_next_session"


def test_acgl_2016_before_open_same_session():
    # Handoff: 2016-02-10T14:17:48Z = 09:17:48 ET -> same session.
    r = resolve_event_session("2016-02-10T14:17:48Z")
    assert str(r.event_session.date()) == "2016-02-10"
    assert r.rule == "same_session_before_or_at_actual_close"


def test_agilent_2016_after_close():
    # Handoff: 2016-11-15T21:08:45Z = 16:08:45 ET -> 2016-11-16.
    r = resolve_event_session("2016-11-15T21:08:45Z")
    assert str(r.event_session.date()) == "2016-11-16"


def test_weekend_to_next_session():
    r = resolve_event_session("2024-02-17T15:00:00Z")  # Saturday
    assert str(r.event_session.date()) == "2024-02-20"


def test_early_close_uses_actual_close():
    # 2024-11-29 (Black Friday) is an XNYS early close.
    session = XNYS.date_to_session("2024-11-29")
    close = XNYS.session_close(session)

    before = resolve_event_session(close - pd.Timedelta(minutes=1))
    after = resolve_event_session(close + pd.Timedelta(minutes=1))

    assert before.event_session == session
    assert after.event_session == XNYS.next_session(session)


def test_event_window_0_2():
    sessions = event_sessions("2025-10-31", 0, 2)
    assert [str(x.date()) for x in sessions] == [
        "2025-10-31",
        "2025-11-03",
        "2025-11-04",
    ]


def test_aapl_2025_arithmetic():
    stock = [-0.003795, -0.004882, 0.003680]
    market = [0.002618, 0.001721, -0.011737]

    stock_bhar, market_bhar, eadret = calculate_eadret(stock, market)

    assert abs(stock_bhar - (-0.005011)) < 2e-6
    assert abs(market_bhar - (-0.007445)) < 2e-6
    assert abs(eadret - 0.002434) < 4e-6
