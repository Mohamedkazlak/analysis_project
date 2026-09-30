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

export type ChartLocale = "en" | "ar";

type PeriodRow = {
  termId?: string;
  termName?: string;
  month?: string;
  year?: number;
  monthNum?: number;
};

const MONTH_EN = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

const MONTH_AR = [
  "يناير",
  "فبراير",
  "مارس",
  "أبريل",
  "مايو",
  "يونيو",
  "يوليو",
  "أغسطس",
  "سبتمبر",
  "أكتوبر",
  "نوفمبر",
  "ديسمبر",
] as const;

const MONTH_ALIAS: Record<string, number> = {
  Jan: 1,
  January: 1,
  Feb: 2,
  February: 2,
  Mar: 3,
  March: 3,
  Apr: 4,
  April: 4,
  May: 5,
  Jun: 6,
  June: 6,
  Jul: 7,
  July: 7,
  Aug: 8,
  August: 8,
  Sep: 9,
  Sept: 9,
  September: 9,
  Oct: 10,
  October: 10,
  Nov: 11,
  November: 11,
  Dec: 12,
  December: 12,
};

const ORG_AR: Record<string, string> = {
  Engineering: "الهندسة",
  "Energy Sciences": "علوم الطاقة",
  "Computer Science": "علوم الحاسب",
  Medicine: "الطب",
  Dentistry: "طب الأسنان",
  "Physical Therapy": "العلاج الطبيعي",
  Veterinary: "الطب البيطري",
  "Visual Arts and Design": "الفنون البصرية والتصميم",
  "Economics and Business Administration": "الاقتصاد وإدارة الأعمال",
};

function monthSort(row: PeriodRow): number {
  return (row.year ?? 0) * 12 + (row.monthNum ?? 0);
}

function monthIndex(row: PeriodRow): number | null {
  if (row.monthNum && row.monthNum >= 1 && row.monthNum <= 12) {
    return row.monthNum;
  }
  if (row.month && MONTH_ALIAS[row.month]) return MONTH_ALIAS[row.month]!;
  return null;
}

export function localizeMonthName(
  month: string | number | null | undefined,
  locale: ChartLocale = "en",
): string {
  if (month == null || month === "") return "";
  if (typeof month === "number") {
    const idx = month - 1;
    if (idx < 0 || idx > 11) return String(month);
    return locale === "ar" ? MONTH_AR[idx]! : MONTH_EN[idx]!;
  }
  const alias = MONTH_ALIAS[month];
  if (alias) {
    return locale === "ar" ? MONTH_AR[alias - 1]! : MONTH_EN[alias - 1]!;
  }
  return month;
}

export function localizeOrgName(
  name: string,
  locale: ChartLocale = "en",
): string {
  if (locale !== "ar") return name;
  return ORG_AR[name] ?? name;
}

export function activityMonthKey(row: PeriodRow): string {
  if (row.year && row.monthNum) {
    return `${row.year}-${String(row.monthNum).padStart(2, "0")}`;
  }
  return row.month ?? "";
}

export function activityMonthLabel(
  row: PeriodRow,
  locale: ChartLocale = "en",
): string {
  const idx = monthIndex(row);
  if (row.year && idx) {
    return `${localizeMonthName(idx, locale)} ${row.year}`;
  }
  if (row.month) return localizeMonthName(row.month, locale);
  return "";
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
  locale: ChartLocale = "en",
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
      label: activityMonthLabel(row, locale),
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
  locale: ChartLocale = "en",
): ActivityChartPoint[] {
  return rows
    .filter((row) => matchesActivityPeriod(row, semesterId, monthKey))
    .sort((a, b) => monthSort(a) - monthSort(b))
    .map((row) => ({
      label: activityMonthLabel(row, locale),
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

export function examScoreRows(
  rows: ExamSummaryRow[],
  locale: ChartLocale = "en",
) {
  return [...rows]
    .sort((a, b) => a.avgScore - b.avgScore || a.course.localeCompare(b.course))
    .map((row) => ({
      ...row,
      label:
        row.month && row.year
          ? `${row.course} · ${activityMonthLabel(row, locale)}`
          : row.course,
      passRate: row.sittings
        ? Math.round((row.passed / row.sittings) * 1000) / 10
        : 0,
    }));
}

/** Latest month compared with the month before it in the visible series. */
export function monthExamChange(
  rows: ActivityChartPoint[],
  locale: ChartLocale = "en",
): {
  label: string;
  value: string;
  sub: string;
  tone: "ink" | "mint" | "rose";
  sentence: string | null;
} {
  const ar = locale === "ar";
  const last = rows[rows.length - 1];
  if (!last) {
    return {
      label: ar ? "التغير عن الشهر السابق" : "Change from previous month",
      value: "—",
      sub: ar ? "لا امتحانات في هذا العرض" : "No exams in this view",
      tone: "ink",
      sentence: null,
    };
  }
  if (rows.length < 2) {
    return {
      label: ar ? "امتحانات هذا الشهر" : "Exams this month",
      value: last.exams.toLocaleString(),
      sub: last.label,
      tone: "ink",
      sentence: null,
    };
  }
  const prev = rows[rows.length - 2];
  if (!prev) {
    return {
      label: ar ? "امتحانات هذا الشهر" : "Exams this month",
      value: last.exams.toLocaleString(),
      sub: last.label,
      tone: "ink",
      sentence: null,
    };
  }
  const delta = last.exams - prev.exams;
  const abs = Math.abs(delta);
  if (delta === 0) {
    return {
      label: ar ? "التغير عن الشهر السابق" : "Change from previous month",
      value: ar ? "بدون تغير" : "No change",
      sub: ar
        ? `${last.label} و${prev.label} كلاهما ${last.exams}`
        : `${last.label} and ${prev.label} both had ${last.exams}`,
      tone: "ink",
      sentence: ar
        ? `${last.label} فيها نفس عدد امتحانات ${prev.label} وهو ${last.exams}.`
        : `${last.label} had the same ${last.exams} exams as ${prev.label}.`,
    };
  }
  return {
    label: ar ? "التغير عن الشهر السابق" : "Change from previous month",
    value: ar
      ? delta > 0
        ? `أكثر بـ ${delta}`
        : `أقل بـ ${abs}`
      : delta > 0
        ? `${delta} more`
        : `${abs} fewer`,
    sub: ar
      ? `${last.label}: ${last.exams} · ${prev.label}: ${prev.exams}`
      : `${last.label} had ${last.exams} · ${prev.label} had ${prev.exams}`,
    tone: delta > 0 ? "mint" : "rose",
    sentence: ar
      ? `${last.label} فيها ${last.exams} امتحانًا، ${delta > 0 ? `أكثر بـ ${abs}` : `أقل بـ ${abs}`} من ${prev.label}.`
      : `${last.label} had ${last.exams} exams, ${abs} ${abs === 1 ? "exam" : "exams"} ${delta > 0 ? "more" : "fewer"} than ${prev.label}.`,
  };
}

export function examActivityInsight(
  exams: ExamSummaryRow[],
  chartRows: ActivityChartPoint[],
  locale: ChartLocale = "en",
): { headline: string; body: string } {
  const ar = locale === "ar";
  if (!exams.length && !chartRows.length) {
    return {
      headline: ar
        ? "لا امتحانات في هذا العرض بعد"
        : "No exams in this view yet",
      body: ar
        ? "لا توجد امتحانات مسجّلة لهذا الشهر أو الفصل، لذلك لا يوجد ما يمكن الإبلاغ عنه."
        : "There are no recorded exams for this month or semester, so there is nothing to report on.",
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
    ? ar
      ? `${last.exams} امتحانًا و${last.participants.toLocaleString()} طالبًا أدوا في ${last.label}`
      : `${last.exams} exams and ${last.participants.toLocaleString()} students sat in ${last.label}`
    : ar
      ? `${exams.length} امتحانًا في هذا العرض`
      : `${exams.length} exams in this view`;

  const parts: string[] = [];
  const change = monthExamChange(chartRows, locale).sentence;
  if (change) parts.push(change);
  if (sat) {
    parts.push(
      ar
        ? `عبر ${sittings.toLocaleString()} جلوسًا، نجح ${passRate}%، مع ${failed.toLocaleString()} رسوبًا و${absent.toLocaleString()} غيابًا.`
        : `Across ${sittings.toLocaleString()} sittings, ${passRate}% passed, with ${failed.toLocaleString()} fails and ${absent.toLocaleString()} absences.`,
    );
  }
  if (busiest) {
    const college = localizeOrgName(busiest.college, locale);
    parts.push(
      ar
        ? `${college} أجرت أكبر عدد من الامتحانات هنا (${busiest.exams}).`
        : `${college} administered the most exams here (${busiest.exams}).`,
    );
  }
  if (weakest) {
    parts.push(
      ar
        ? `أدنى متوسط درجة هو ${weakest.avgScore}% في ${weakest.course} ${weakest.title}.`
        : `The lowest mean score is ${weakest.avgScore}% on ${weakest.course} ${weakest.title}.`,
    );
  }

  return {
    headline,
    body:
      parts.join(" ") ||
      (ar
        ? "نشاط الامتحانات متاح للفترة المحددة."
        : "Exam activity is available for the selected period."),
  };
}
