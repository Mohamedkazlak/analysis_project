import { describe, expect, it } from "vitest";
import {
  collegeOptions,
  examChartRows,
  filterByCollege,
  selectedCollege,
  semesterCoverage,
  semesterPassRateNote,
} from "./student-performance";

describe("performance college filter", () => {
  const rows = [
    { college: "Medicine", collegeId: "prog-med" },
    { college: "Computer Science", collegeId: "prog-cs" },
    { college: "Medicine", collegeId: "prog-med" },
  ];

  it("lists each college once, by name", () => {
    expect(collegeOptions(rows)).toEqual([
      { value: "prog-cs", label: "Computer Science" },
      { value: "prog-med", label: "Medicine" },
    ]);
  });

  it("keeps every row when the filter is all colleges", () => {
    expect(filterByCollege(rows, "all")).toHaveLength(3);
    expect(filterByCollege(rows, "prog-med")).toEqual([
      { college: "Medicine", collegeId: "prog-med" },
      { college: "Medicine", collegeId: "prog-med" },
    ]);
  });

  it("keeps a repeated course distinct on the chart axis", () => {
    expect(
      examChartRows([
        { course: "VTM", exam: "Midterm" },
        { course: "VTM", exam: "Final" },
        { course: "MED 101", exam: "Final" },
      ]).map((row) => row.label),
    ).toEqual(["VTM · Midterm", "VTM · Final", "MED 101"]);
  });

  it("falls back to the first college when the choice is gone", () => {
    const options = collegeOptions(rows);
    expect(selectedCollege(options, "prog-med")).toBe("prog-med");
    expect(selectedCollege(options, "missing")).toBe("prog-cs");
  });
});

describe("semester pass-rate note", () => {
  it("names both semesters when a college has exams in each", () => {
    expect(
      semesterCoverage([
        { current: 80, previous: null },
        { current: null, previous: 60 },
      ]),
    ).toBe("both");
    expect(semesterPassRateNote("both", "Spring 2026", "Fall 2025")).toContain(
      "Spring 2026",
    );
  });

  it("says when the college sat exams in only one semester", () => {
    expect(semesterCoverage([{ current: 88, previous: null }])).toBe("current");
    expect(
      semesterPassRateNote("current", "Spring 2026", "Fall 2025"),
    ).toContain("no scored exams in Fall 2025");
  });
});
