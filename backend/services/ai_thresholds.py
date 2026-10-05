"""Single source for analytics / AI card thresholds.

Cards, seed stories, and warning rules must read these names — not scatter
magic numbers. Pass mark stays aligned with institution_settings (60).
"""

from __future__ import annotations

from core.utils import PASS_MARK

# Course / college pass-rate review threshold (warnings).
PASS_RATE_THRESHOLD = 70.0

# Attendance: medium when below WATCH; high when below THRESHOLD.
ATTENDANCE_WATCH = 90.0
ATTENDANCE_THRESHOLD = 80.0

DISCRIMINATION_THRESHOLD = 0.2
DECLINE_THRESHOLD = 10.0

# Forecast needs this many yearly averages in scope.
MIN_FORECAST_OBSERVATIONS = 3

__all__ = [
    "PASS_MARK",
    "PASS_RATE_THRESHOLD",
    "ATTENDANCE_WATCH",
    "ATTENDANCE_THRESHOLD",
    "DISCRIMINATION_THRESHOLD",
    "DECLINE_THRESHOLD",
    "MIN_FORECAST_OBSERVATIONS",
]
