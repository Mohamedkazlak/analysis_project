import { describe, expect, it } from "vitest";
import {
  activityMonthOptions,
  activitySemesterOptions,
  examActivityInsight,
  examsByCollege,
  examScoreRows,
  filterActivityTrend,
  monthExamChange,
  filterExamSummaries,
} from "./exam-activity-chart";

const rows = [
  {
    month: "Feb",
    year: 2026,
    monthNum: 2,
    termId: "term-2025-spring",
    termName: "Spring 2026",
    exams: 4,
    participants: 80,
  },
  {
    month: "Mar",
    year: 2026,
    monthNum: 3,
    termId: "term-2025-spring",
    termName: "Spring 2026",
    exams: 10,
    participants: 200,
  },
  {
    month: "Oct",
    year: 2025,
    monthNum: 10,
    termId: "term-2025-fall",
    termName: "Fall 2025",
    exams: 3,
    participants: 40,
  },
];

describe("exam-activity chart filters", () => {
  it("lists semesters in date order", () => {
    expect(activitySemesterOptions(rows)).toEqual([
      { value: "term-2025-fall", label: "Fall 2025" },
      { value: "term-2025-spring", label: "Spring 2026" },
    ]);
  });

  it("lists months for the selected semester", () => {
    expect(activityMonthOptions(rows, "term-2025-spring")).toEqual([
      { value: "2026-02", label: "Feb 2026" },
      { value: "2026-03", label: "Mar 2026" },
    ]);
    expect(activityMonthOptions(rows, "term-2025-spring", "ar")).toEqual([
      { value: "2026-02", label: "فبراير 2026" },
      { value: "2026-03", label: "مارس 2026" },
    ]);
  });

  it("filters the series by semester and month", () => {
    expect(
      filterActivityTrend(rows, "term-2025-spring", "all").map((r) => r.label),
    ).toEqual(["Feb 2026", "Mar 2026"]);
    expect(filterActivityTrend(rows, "all", "2025-10")).toEqual([
      { label: "Oct 2025", exams: 3, participants: 40 },
    ]);
    expect(
      filterActivityTrend(rows, "term-2025-spring", "all", "ar").map(
        (r) => r.label,
      ),
    ).toEqual(["فبراير 2026", "مارس 2026"]);
  });
});

describe("exam summaries", () => {
  const exams = [
    {
      examId: "e1",
      title: "Midterm I",
      course: "CS101",
      college: "Computer Science",
      termId: "term-2025-spring",
      termName: "Spring 2026",
      month: "Feb",
      year: 2026,
      monthNum: 2,
      sittings: 40,
      passed: 32,
      failed: 8,
      absent: 2,
      late: 1,
      avgScore: 71,
    },
    {
      examId: "e2",
      title: "Final",
      course: "CS101",
      college: "Computer Science",
      termId: "term-2025-spring",
      termName: "Spring 2026",
      month: "Mar",
      year: 2026,
      monthNum: 3,
      sittings: 38,
      passed: 30,
      failed: 8,
      absent: 4,
      late: 0,
      avgScore: 68,
    },
    {
      examId: "e3",
      title: "Anatomy",
      course: "MED101",
      college: "Medicine",
      termId: "term-2025-fall",
      termName: "Fall 2025",
      month: "Oct",
      year: 2025,
      monthNum: 10,
      sittings: 20,
      passed: 18,
      failed: 2,
      absent: 1,
      late: 0,
      avgScore: 80,
    },
  ];

  it("rolls exam counts and sittings up by college", () => {
    const spring = filterExamSummaries(exams, "term-2025-spring", "all");
    expect(examsByCollege(spring)).toEqual([
      {
        college: "Computer Science",
        exams: 2,
        sittings: 78,
        sittingsPerExam: 39,
        passed: 62,
        failed: 16,
        absent: 6,
        avgScore: 69.5,
      },
    ]);
  });

  it("orders exams from lowest average score to highest", () => {
    expect(examScoreRows(exams).map((row) => row.examId)).toEqual([
      "e2",
      "e1",
      "e3",
    ]);
  });

  it("compares the latest month with the month before it", () => {
    expect(
      monthExamChange(filterActivityTrend(rows, "term-2025-spring", "all")),
    ).toMatchObject({
      value: "6 more",
      sub: "Mar 2026 had 10 · Feb 2026 had 4",
    });
    expect(
      monthExamChange(
        filterActivityTrend(rows, "term-2025-spring", "all", "ar"),
        "ar",
      ),
    ).toMatchObject({
      value: "أكثر بـ 6",
      sub: "مارس 2026: 10 · فبراير 2026: 4",
    });
  });

  it("summarises exam activity for the AI insight card", () => {
    const insight = examActivityInsight(
      filterExamSummaries(exams, "term-2025-spring", "all"),
      filterActivityTrend(rows, "term-2025-spring", "all"),
    );
    expect(insight.headline).toBe("10 exams and 200 students sat in Mar 2026");
    expect(insight.body).toContain("6 exams more than Feb 2026");
    expect(insight.body).toContain("79.5% passed");
    expect(insight.body).toContain(
      "Computer Science administered the most exams",
    );
    expect(insight.body).toContain("CS101 Final");

    const arInsight = examActivityInsight(
      filterExamSummaries(exams, "term-2025-spring", "all"),
      filterActivityTrend(rows, "term-2025-spring", "all", "ar"),
      "ar",
    );
    expect(arInsight.headline).toContain("مارس 2026");
    expect(arInsight.body).toContain("فبراير 2026");
    expect(arInsight.body).toContain("علوم الحاسب");
  });
});
