export type ActivityTrendRow = {
  month: string;
  exams: number;
  participants: number;
  year?: number;
  monthNum?: number;
  termId?: string;
  termName?: string;
};

export type ExamSummaryRow = {
  examId: string;
  title: string;
  course: string;
  college: string;
  termId?: string;
  termName?: string;
  month?: string;
  year?: number;
  monthNum?: number;
  sittings: number;
  passed: number;
  failed: number;
  absent: number;
  late: number;
  avgScore: number;
};

export type ActivityChartPoint = {
  label: string;
  exams: number;
  participants: number;
};

export type ExamCollegeRow = {
  college: string;
  exams: number;
  sittings: number;
  sittingsPerExam: number;
  passed: number;
  failed: number;
  absent: number;
  avgScore: number;
};

type PeriodRow = {
  termId?: string;
  termName?: string;
  month?: string;
  year?: number;
  monthNum?: number;
};

function monthSort(row: PeriodRow): number {
  return (row.year ?? 0) * 12 + (row.monthNum ?? 0);
}

export function activityMonthKey(row: PeriodRow): string {
  if (row.year && row.monthNum) {
    return `${row.year}-${String(row.monthNum).padStart(2, "0")}`;
  }
  return row.month ?? "";
}

export function activityMonthLabel(row: PeriodRow): string {
  return row.year && row.month ? `${row.month} ${row.year}` : (row.month ?? "");
}

export function matchesActivityPeriod(
  row: PeriodRow,
  semesterId: string,
  monthKey: string,
): boolean {
  if (semesterId !== "all" && row.termId !== semesterId) return false;
  if (monthKey !== "all" && activityMonthKey(row) !== monthKey) return false;
  return true;
}

export function activitySemesterOptions(rows: PeriodRow[]): {
  value: string;
  label: string;
}[] {
  const seen = new Set<string>();
  const options: { value: string; label: string; sort: number }[] = [];
  for (const row of rows) {
    const value = row.termId;
    if (!value || seen.has(value)) continue;
    seen.add(value);
    options.push({
      value,
      label: row.termName || value,
      sort: monthSort(row),
    });
  }
  return options
    .sort((a, b) => a.sort - b.sort)
    .map(({ value, label }) => ({ value, label }));
}

export function activityMonthOptions(
  rows: PeriodRow[],
  semesterId: string,
): { value: string; label: string }[] {
  const scoped =
    semesterId === "all"
      ? rows
      : rows.filter((row) => row.termId === semesterId);
  const seen = new Set<string>();
  const options: { value: string; label: string; sort: number }[] = [];
  for (const row of scoped) {
    const value = activityMonthKey(row);
    if (!value || seen.has(value)) continue;
    seen.add(value);
    options.push({
      value,
      label: activityMonthLabel(row),
      sort: monthSort(row),
    });
  }
  return options
    .sort((a, b) => a.sort - b.sort)
    .map(({ value, label }) => ({ value, label }));
}

export function filterActivityTrend(
  rows: ActivityTrendRow[],
  semesterId: string,
  monthKey: string,
): ActivityChartPoint[] {
  return rows
    .filter((row) => matchesActivityPeriod(row, semesterId, monthKey))
    .sort((a, b) => monthSort(a) - monthSort(b))
    .map((row) => ({
      label: activityMonthLabel(row),
      exams: row.exams,
      participants: row.participants,
    }));
}

export function filterExamSummaries(
  rows: ExamSummaryRow[],
  semesterId: string,
  monthKey: string,
): ExamSummaryRow[] {
  return rows
    .filter((row) => matchesActivityPeriod(row, semesterId, monthKey))
    .sort(
      (a, b) => monthSort(a) - monthSort(b) || a.course.localeCompare(b.course),
    );
}

export function examsByCollege(rows: ExamSummaryRow[]): ExamCollegeRow[] {
  const map = new Map<
    string,
    ExamCollegeRow & { scoreTotal: number; scoreWeight: number }
  >();
  for (const row of rows) {
    const cur = map.get(row.college) ?? {
      college: row.college,
      exams: 0,
      sittings: 0,
      sittingsPerExam: 0,
      passed: 0,
      failed: 0,
      absent: 0,
      avgScore: 0,
      scoreTotal: 0,
      scoreWeight: 0,
    };
    cur.exams += 1;
    cur.sittings += row.sittings;
    cur.passed += row.passed;
    cur.failed += row.failed;
    cur.absent += row.absent;
    cur.scoreTotal += row.avgScore * row.sittings;
    cur.scoreWeight += row.sittings;
    map.set(row.college, cur);
  }
  return [...map.values()]
    .map((row) => ({
      college: row.college,
      exams: row.exams,
      sittings: row.sittings,
      sittingsPerExam: row.exams ? Math.round(row.sittings / row.exams) : 0,
      passed: row.passed,
      failed: row.failed,
      absent: row.absent,
      avgScore: row.scoreWeight
        ? Math.round((row.scoreTotal / row.scoreWeight) * 10) / 10
        : 0,
    }))
    .sort((a, b) => b.exams - a.exams || a.college.localeCompare(b.college));
}

export function examScoreRows(rows: ExamSummaryRow[]) {
  return [...rows]
    .sort((a, b) => a.avgScore - b.avgScore || a.course.localeCompare(b.course))
    .map((row) => ({
      ...row,
      label:
        row.month && row.year
          ? `${row.course} · ${row.month} ${row.year}`
          : row.course,
      passRate: row.sittings
        ? Math.round((row.passed / row.sittings) * 1000) / 10
        : 0,
    }));
}

/** Latest month compared with the month before it in the visible series. */
export function monthExamChange(rows: ActivityChartPoint[]): {
  label: string;
  value: string;
  sub: string;
  tone: "ink" | "mint" | "rose";
  sentence: string | null;
} {
  const last = rows[rows.length - 1];
  if (!last) {
    return {
      label: "Change from previous month",
      value: "—",
      sub: "No exams in this view",
      tone: "ink",
      sentence: null,
    };
  }
  if (rows.length < 2) {
    return {
      label: "Exams this month",
      value: last.exams.toLocaleString(),
      sub: last.label,
      tone: "ink",
      sentence: null,
    };
  }
  const prev = rows[rows.length - 2];
  if (!prev) {
    return {
      label: "Exams this month",
      value: last.exams.toLocaleString(),
      sub: last.label,
      tone: "ink",
      sentence: null,
    };
  }
  const delta = last.exams - prev.exams;
  const countLabel = `${Math.abs(delta)} ${Math.abs(delta) === 1 ? "exam" : "exams"}`;
  if (delta === 0) {
    return {
      label: "Change from previous month",
      value: "No change",
      sub: `${last.label} and ${prev.label} both had ${last.exams}`,
      tone: "ink",
      sentence: `${last.label} had the same ${last.exams} exams as ${prev.label}.`,
    };
  }
  return {
    label: "Change from previous month",
    value: delta > 0 ? `${delta} more` : `${Math.abs(delta)} fewer`,
    sub: `${last.label} had ${last.exams} · ${prev.label} had ${prev.exams}`,
    tone: delta > 0 ? "mint" : "rose",
    sentence: `${last.label} had ${last.exams} exams, ${countLabel} ${delta > 0 ? "more" : "fewer"} than ${prev.label}.`,
  };
}

export function examActivityInsight(
  exams: ExamSummaryRow[],
  chartRows: ActivityChartPoint[],
): { headline: string; body: string } {
  if (!exams.length && !chartRows.length) {
    return {
      headline: "No exams in this view yet",
      body: "There are no recorded exams for this month or semester, so there is nothing to report on.",
    };
  }

  const sittings = exams.reduce((sum, exam) => sum + exam.sittings, 0);
  const passed = exams.reduce((sum, exam) => sum + exam.passed, 0);
  const failed = exams.reduce((sum, exam) => sum + exam.failed, 0);
  const absent = exams.reduce((sum, exam) => sum + exam.absent, 0);
  const sat = passed + failed;
  const passRate = sat ? Math.round((passed / sat) * 1000) / 10 : 0;
  const colleges = examsByCollege(exams);
  const busiest = colleges[0];
  const weakest = [...exams].sort(
    (a, b) => a.avgScore - b.avgScore || a.course.localeCompare(b.course),
  )[0];
  const last = chartRows[chartRows.length - 1];

  const headline = last
    ? `${last.exams} exams and ${last.participants.toLocaleString()} students sat in ${last.label}`
    : `${exams.length} exams in this view`;

  const parts: string[] = [];
  const change = monthExamChange(chartRows).sentence;
  if (change) parts.push(change);
  if (sat) {
    parts.push(
      `Across ${sittings.toLocaleString()} sittings, ${passRate}% passed, with ${failed.toLocaleString()} fails and ${absent.toLocaleString()} absences.`,
    );
  }
  if (busiest) {
    parts.push(
      `${busiest.college} administered the most exams here (${busiest.exams}).`,
    );
  }
  if (weakest) {
    parts.push(
      `The lowest mean score is ${weakest.avgScore}% on ${weakest.course} ${weakest.title}.`,
    );
  }

  return {
    headline,
    body:
      parts.join(" ") || "Exam activity is available for the selected period.",
  };
}
