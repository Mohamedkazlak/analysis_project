export type CollegeScoped = {
  college: string;
  collegeId: string;
};

export function collegeOptions(rows: CollegeScoped[]): {
  value: string;
  label: string;
}[] {
  const seen = new Map<string, string>();
  for (const row of rows) {
    if (row.collegeId && !seen.has(row.collegeId)) {
      seen.set(row.collegeId, row.college);
    }
  }
  return [...seen.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function filterByCollege<T extends { collegeId: string }>(
  rows: T[],
  collegeId: string,
): T[] {
  if (!collegeId || collegeId === "all") return rows;
  return rows.filter((row) => row.collegeId === collegeId);
}

/** Course code on the axis. Repeat codes keep the exam title so bars stay distinct. */
export function examChartRows<T extends { course: string; exam: string }>(
  rows: T[],
): (T & { label: string })[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    counts.set(row.course, (counts.get(row.course) ?? 0) + 1);
  }
  return rows.map((row) => ({
    ...row,
    label:
      (counts.get(row.course) ?? 0) > 1
        ? `${row.course} · ${row.exam}`
        : row.course,
  }));
}

/** Keep a chosen college when it is still in the list; otherwise the first. */
export function selectedCollege(
  options: { value: string }[],
  chosen: string,
): string {
  if (options.some((option) => option.value === chosen)) return chosen;
  return options[0]?.value ?? "";
}

export function semesterCoverage<
  T extends { current: number | null; previous: number | null },
>(rows: T[]): "both" | "current" | "previous" | "none" {
  const hasCurrent = rows.some((row) => row.current != null);
  const hasPrevious = rows.some((row) => row.previous != null);
  if (hasCurrent && hasPrevious) return "both";
  if (hasCurrent) return "current";
  if (hasPrevious) return "previous";
  return "none";
}

export function semesterPassRateNote(
  coverage: ReturnType<typeof semesterCoverage>,
  currentTerm: string | null,
  previousTerm: string | null,
  copy?: {
    thisSemester: string;
    lastSemester: string;
    both: string;
    currentOnly: string;
    previousOnly: string;
    none: string;
  },
): string {
  const current = currentTerm ?? copy?.thisSemester ?? "this semester";
  const previous = previousTerm ?? copy?.lastSemester ?? "last semester";
  if (coverage === "both") {
    return (
      copy?.both ??
      "Pass rate of scored sittings in {current} compared with {previous}."
    )
      .replace("{current}", current)
      .replace("{previous}", previous);
  }
  if (coverage === "current") {
    return (
      copy?.currentOnly ??
      "Pass rate of scored sittings in {current}. This college has no scored exams in {previous}."
    )
      .replace("{current}", current)
      .replace("{previous}", previous);
  }
  if (coverage === "previous") {
    return (
      copy?.previousOnly ??
      "Pass rate of scored sittings in {previous}. This college has no scored exams in {current}."
    )
      .replace("{current}", current)
      .replace("{previous}", previous);
  }
  return copy?.none ?? "No scored exams in this college for these semesters.";
}
