import asyncpg

from core.utils import round1
from services.gpa import (
    TranscriptCourse,
    compute_gpa,
    letter_from_percent,
    standing_from_gpa,
)


async def build_profile_years(db: asyncpg.Connection, student_id: str) -> dict:
    rows = await db.fetch(
        """
        SELECT
            t.academic_year_id AS year,
            y.label AS year_label,
            c.name AS course,
            c.code,
            t.average::float AS average,
            t.letter_grade,
            t.credits,
            COALESCE(c.counted_in_cumulative_gpa, true) AS counted_in_cumulative_gpa,
            COALESCE(c.pass_fail_subject, false) AS pass_fail_subject
        FROM transcript_entries t
        JOIN courses c ON c.id = t.course_id
        JOIN academic_years y ON y.id = t.academic_year_id
        WHERE t.student_id = $1
        ORDER BY t.academic_year_id, c.code
        """,
        student_id,
    )
    by_year: dict[str, list] = {}
    labels: dict[str, str] = {}
    for r in rows:
        by_year.setdefault(r["year"], []).append(r)
        labels[r["year"]] = r["year_label"]

    years = []
    year_trend = []
    course_names: dict[str, dict[str, float]] = {}
    ordered_years = sorted(by_year.keys())
    for year_id in ordered_years:
        course_rows = by_year[year_id]
        entries = [
            TranscriptCourse(
                course_id=r["code"],
                course=r["course"],
                code=r["code"],
                average=float(r["average"]),
                letter_grade=r["letter_grade"]
                or letter_from_percent(float(r["average"])),
                credits=int(r["credits"]),
                counted_in_cumulative_gpa=bool(r["counted_in_cumulative_gpa"]),
                pass_fail_subject=bool(r["pass_fail_subject"]),
            )
            for r in course_rows
        ]
        gpa = compute_gpa(entries)
        percents = [e.average for e in entries]
        year_avg = round1(sum(percents) / len(percents)) if percents else 0
        years.append(
            {
                "year": year_id,
                "yearLabel": labels[year_id],
                "average": year_avg,
                "gpa": gpa.gpa if gpa.gpa is not None else 0.0,
                "classAverage": year_avg,
                "examsTaken": len(entries),
                "passRate": (
                    round1(
                        100 * sum(1 for e in entries if e.average >= 60) / len(entries)
                    )
                    if entries
                    else 0
                ),
                "attendance": 0,
                "credits": sum(e.credits for e in entries),
                "standing": standing_from_gpa(gpa.gpa, year_avg),
                "courses": [
                    {
                        "course": e.course,
                        "code": e.code,
                        "average": e.average,
                        "grade": e.letter_grade,
                        "credits": e.credits,
                    }
                    for e in entries
                ],
            }
        )
        year_trend.append(
            {"year": labels[year_id], "student": year_avg, "cohort": year_avg}
        )
        for e in entries:
            course_names.setdefault(e.course, {})[year_id] = e.average

    course_matrix = [
        {"course": name, "values": [vals.get(y) for y in ordered_years]}
        for name, vals in course_names.items()
    ]
    all_entries = [
        TranscriptCourse(
            course_id=r["code"],
            course=r["course"],
            code=r["code"],
            average=float(r["average"]),
            letter_grade=r["letter_grade"] or letter_from_percent(float(r["average"])),
            credits=int(r["credits"]),
            counted_in_cumulative_gpa=bool(r["counted_in_cumulative_gpa"]),
            pass_fail_subject=bool(r["pass_fail_subject"]),
        )
        for r in rows
    ]
    cumulative = compute_gpa(all_entries)
    credit_total = sum(e.credits for e in all_entries)
    overall_average = (
        round1(sum(e.average * e.credits for e in all_entries) / credit_total)
        if credit_total
        else 0
    )
    return {
        "years": years,
        "yearTrend": year_trend,
        "courseMatrix": course_matrix,
        "gpa": cumulative.gpa if cumulative.gpa is not None else 0.0,
        "totalCredits": cumulative.gpa_credits,
        "standing": standing_from_gpa(cumulative.gpa, overall_average),
        "overallAverage": overall_average,
    }
