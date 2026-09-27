"""Short table descriptions sent to the SQL model. Only allowlisted tables are included."""

TABLE_DOCS = {
    "org_units": (
        "University, sector, and program tree. College in the product is level = program. "
        "Columns: id, parent_id, level (university/sector/program), code, name."
    ),
    "academic_years": "id, label, start_date, end_date, is_current.",
    "terms": "id, academic_year_id, code, name, start_date, end_date.",
    "people": "id, full_name, email. Shared identity for staff and students.",
    "staff": "person_id (PK), title, org_unit_id.",
    "students": (
        "id, person_id, student_number, program_id (program-level org unit), "
        "section, cohort_year, status (active/graduated/withdrawn)."
    ),
    "courses": (
        "id, program_id, code, name, credits, year_level. "
        "A curriculum in the product is one courses row."
    ),
    "course_offerings": (
        "id, course_id, academic_year_id, term_id, instructor_id. "
        "instructor_id is not the authorization source for professors."
    ),
    "course_sections": "id, offering_id, code.",
    "staff_course_assignments": (
        "staff_person_id, course_id. This is the professor's assigned-course relationship."
    ),
    "enrollments": "id, student_id, offering_id, section_id, enrolled_at.",
    "exams": (
        "id, offering_id, title, scheduled_at, duration_minutes, question_count, "
        "pass_mark, status (scheduled/in_progress/closing/closed)."
    ),
    "questions": "id, exam_id, number, topic, prompt, max_score.",
    "exam_attempts": (
        "id, exam_id, student_id, enrollment_id, score (0-100), time_taken_min, "
        "started_at, ended_at, status (absent/in_progress/submitted/void)."
    ),
    "attempt_answers": "attempt_id, question_id, is_correct, points.",
    "integrity_flags": (
        "id, attempt_id, flag_type (multiple_attempts/fast_submission/late_start/"
        "shared_ip/similar_answers), detail, created_at."
    ),
    "transcript_entries": (
        "Closed grades. id, student_id, course_id, academic_year_id, "
        "average (0-100), letter_grade, credits."
    ),
}


def build_schema_context(allowed_tables: list[str] | set[str]) -> str:
    lines = [
        f"- {name}: {TABLE_DOCS[name]}"
        for name in sorted(allowed_tables)
        if name in TABLE_DOCS
    ]
    return "\n".join(lines)
