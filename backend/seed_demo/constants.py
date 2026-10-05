"""Demo storyboard seeder.

Modes: dry-run | apply | reset-synthetic
Owned row id prefix: demosb-
Only writes is_synthetic=true assessment rows, or demosb- prefixed rows in
tables without the flag. Never modifies is_synthetic=false rows.
"""

from __future__ import annotations

SEED_CONSTANT = 20250930
OWNED_PREFIX = "demosb-"

# Existing synthetic AIM303 exam we rebuild (is_synthetic=true).
AIM303_COURSE_ID = "crs-cs-aim303"
AIM303_OFFERING_2025 = "off-crs-cs-aim303-2025/26-fall"
AIM303_EXAM_2025 = "syn-exam-off-crs-cs-aim303-2025/26-fall"
AIM303_SECTION_A = "sec-crs-cs-aim303-fall-A"
AIM303_SECTION_B = "demosb-sec-aim303-fall-B"

# S5: synthetic Vet course near review threshold (real 106VTM left alone).
S5_COURSE_ID = "demosb-crs-vet-vtm210"
S5_COURSE_CODE = "210VTM"

PROGRAMS = {
    "cs": "prog-computer-science",
    "eng": "prog-engineering",
    "vet": "prog-veterinary",
    "art": "prog-visual-arts",
    "ene": "prog-energy-sciences",
    "med": "prog-medicine",
    "den": "prog-dentistry",
    "pt": "prog-physical-therapy",
    "eco": "prog-economics",
}

YEARS = ("2023/24", "2024/25", "2025/26")
TERMS = {
    "2023/24": "term-2023-spring",
    "2024/25": "term-2024-spring",
    "2025/26": "term-2025-fall",
}

# Calibrated from live real rows (Phase 0).
REAL_ATTEMPT_MEAN = 56.18
REAL_ATTEMPT_SD = 30.89
REAL_TRANSCRIPT_MEAN = 58.92
REAL_TRANSCRIPT_SD = 31.09

# Story targets (tolerances in answer_key / verify).
S1_PASS_2025 = 0.50
S1_PASS_2024 = 0.61
S1_PASS_2023 = 0.72
S1_SECTION_GAP = 15.0
S1_WEAK_TOPIC_RATE = 0.28
S1_STRONG_TOPIC_RATE = 0.72

S2_ENG_PASS = {"2023/24": 0.76, "2024/25": 0.72, "2025/26": 0.68}
S3_CS_PASS = {"2023/24": 0.70, "2024/25": 0.73}  # 2025/26 = real, untouched
S5_PASS = 0.68

# Letter scale inferred from real distribution bands.
LETTER_BANDS = (
    (95, "A+"),
    (90, "A"),
    (85, "A-"),
    (80, "B+"),
    (75, "B"),
    (70, "C+"),
    (65, "C"),
    (60, "D+"),
    (55, "D"),
    (50, "D-"),
    (0, "Failed (Overall)"),
)
