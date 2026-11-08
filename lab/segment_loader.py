"""Segment guard for Protocol v1.2 (T4, T5, H1-H7). Pure time logic; reads no market data.

Access types (H6, as clarified 2026-11-08):
  ENTRY / LABEL / OUTCOME  -> only inside the assigned segment (entry window for starts; outcome must end inside the
                              segment data range); horizon <= H_max (30 d)
  FEATURE LOOKBACK at t    -> any research-period history strictly before t (earlier segments and embargoes allowed),
                              never before RESEARCH_START (Dec-2023 warm-up is forbidden here, T3), never >= t
  FUTURE timestamp         -> always refused
  Final Holdout            -> sealed (H7): every access raises unless the holdout was opened by the logged one-time event
"""
import datetime as dt

UTC = dt.timezone.utc
H = dt.timedelta(hours=1)
H_MAX = dt.timedelta(days=30)
RESEARCH_START = dt.datetime(2024, 1, 1, tzinfo=UTC)
T2_END = dt.datetime(2026, 10, 31, 16, tzinfo=UTC)


def _t(y, m, d, h=0):
    return dt.datetime(y, m, d, h, tzinfo=UTC)


SEGMENTS = {
    # name: (data_start, data_end_exclusive, entry_start, entry_end_exclusive)
    "development": (_t(2024, 1, 1), _t(2025, 9, 1), _t(2024, 1, 1), _t(2025, 8, 2)),
    "validation": (_t(2025, 9, 8), _t(2026, 4, 1), _t(2025, 9, 8), _t(2026, 3, 2)),
    "holdout": (_t(2026, 4, 8), T2_END, _t(2026, 4, 8), _t(2026, 10, 1, 16)),
}
EMBARGOES = [(_t(2025, 9, 1), _t(2025, 9, 8)), (_t(2026, 4, 1), _t(2026, 4, 8))]


class GuardError(Exception):
    pass


class SegmentGuard:
    def __init__(self, segment, holdout_opened=False):
        if segment not in SEGMENTS:
            raise GuardError(f"unknown segment {segment}")
        if segment == "holdout" and not holdout_opened:
            raise GuardError("Final Holdout is sealed (H7)")
        self.seg = segment
        self.ds, self.de, self.es, self.ee = SEGMENTS[segment]

    # --- entries and labels (H1, H2, H3)
    def check_entry(self, t):
        if not (self.es <= t < self.ee):
            raise GuardError(f"entry/label start {t} outside entry window of {self.seg}")
        return t

    def check_outcome(self, t, horizon):
        self.check_entry(t)
        if horizon <= dt.timedelta(0) or horizon > H_MAX:
            raise GuardError(f"horizon {horizon} not in (0, H_max]")
        if t + horizon > self.de:
            raise GuardError(f"outcome [{t}, {t + horizon}] crosses the end of {self.seg}")
        return (t, t + horizon)

    def check_outcome_candles(self, t, horizon, candle_starts, candle_len=H):
        s, e = self.check_outcome(t, horizon)
        for c in candle_starts:
            if c < s or c + candle_len > e:
                raise GuardError(f"outcome candle {c} outside [{s}, {e}] (T5)")
        return True

    # --- features (H5)
    def check_feature(self, t, lookback_starts, candle_len=H):
        """t: decision time; lookback_starts: start times of candles used. Each must close at or before t (T5),
        and start at or after RESEARCH_START (no Dec-2023 warm-up, T3). Earlier segments/embargoes are allowed."""
        for c in lookback_starts:
            if c + candle_len > t:
                raise GuardError(f"feature candle {c} not closed by decision time {t} (future)")
            if c < RESEARCH_START:
                raise GuardError(f"feature candle {c} before research start (Dec-2023 warm-up forbidden, T3)")
        return True

    # --- Market Intelligence / feature discovery / regime fitting (H6): Development only
    def check_research_statistic(self, day_start, used_starts, candle_len=H):
        if self.seg != "development":
            raise GuardError(f"MI / feature discovery / regime fitting not allowed on {self.seg} (H6)")
        if not (self.ds <= day_start < self.de):
            raise GuardError(f"statistic day {day_start} outside Development")
        return self.check_feature(day_start, used_starts, candle_len)
