import { describe, expect, it } from "vitest";
import {
  coursesCurriculumSubtitle,
  coursesScopeMessage,
  coursesScopeReady,
  courseStanding,
  courseStandingLabel,
  filterByStanding,
  sortComparisonRows,
  toggleComparisonSort,
} from "./course-performance";

describe("course standing", () => {
  it("treats 75% and above as on track", () => {
    expect(courseStanding(75)).toBe("on_track");
    expect(courseStanding(90)).toBe("on_track");
    expect(courseStandingLabel("on_track")).toBe("On track");
  });

  it("treats below 75% as needs support", () => {
    expect(courseStanding(74.9)).toBe("needs_support");
    expect(courseStanding(0)).toBe("needs_support");
    expect(courseStandingLabel("needs_support")).toBe("Needs support");
  });

  it("filters comparison rows by standing", () => {
    const rows = [
      { course: "Algorithms", passRate: 82 },
      { course: "Calculus", passRate: 61 },
    ];
    expect(filterByStanding(rows, "all")).toHaveLength(2);
    expect(filterByStanding(rows, "on_track").map((row) => row.course)).toEqual(
      ["Algorithms"],
    );
    expect(
      filterByStanding(rows, "needs_support").map((row) => row.course),
    ).toEqual(["Calculus"]);
  });
});

describe("section comparison sort", () => {
  const rows = [
    {
      college: "Science",
      course: "Calculus",
      enrolled: 12,
      average: 81,
      passRate: 90,
    },
    {
      college: "Engineering",
      course: "Algorithms",
      enrolled: 40,
      average: 64,
      passRate: 55,
    },
    {
      college: "Science",
      course: "Biology",
      enrolled: 8,
      average: 70,
      passRate: 75,
    },
  ];

  it("sorts names A → Z and numbers high → low by default direction", () => {
    expect(
      sortComparisonRows(rows, "course", true).map((row) => row.course),
    ).toEqual(["Algorithms", "Biology", "Calculus"]);
    expect(
      sortComparisonRows(rows, "college", true).map((row) => ({
        college: row.college,
        course: row.course,
      })),
    ).toEqual([
      { college: "Engineering", course: "Algorithms" },
      { college: "Science", course: "Biology" },
      { college: "Science", course: "Calculus" },
    ]);
    expect(
      sortComparisonRows(rows, "college", false).map((row) => row.college),
    ).toEqual(["Science", "Science", "Engineering"]);
    expect(
      sortComparisonRows(rows, "enrolled", false).map((row) => row.course),
    ).toEqual(["Algorithms", "Calculus", "Biology"]);
  });

  it("keeps courses A → Z inside a college when sorting by standing", () => {
    expect(
      sortComparisonRows(rows, "standing", false).map((row) => row.course),
    ).toEqual(["Biology", "Calculus", "Algorithms"]);
  });

  it("flips direction on the same column and starts A → Z for names", () => {
    expect(toggleComparisonSort("average", false, "average")).toEqual({
      key: "average",
      asc: true,
    });
    expect(toggleComparisonSort("average", false, "course")).toEqual({
      key: "course",
      asc: true,
    });
    expect(toggleComparisonSort("average", false, "college")).toEqual({
      key: "college",
      asc: true,
    });
    expect(toggleComparisonSort("course", true, "enrolled")).toEqual({
      key: "enrolled",
      asc: false,
    });
  });
});

describe("courses scope", () => {
  it("lets professors open their assigned curriculum", () => {
    expect(coursesScopeReady("professor", {})).toBe(true);
  });

  it("shows college-wide curriculum for a program director before filters", () => {
    expect(coursesScopeReady("program_director", {})).toBe(true);
    expect(coursesCurriculumSubtitle("program_director", {})).toBe(
      "All curriculum in this college",
    );
    expect(
      coursesCurriculumSubtitle("program_director", {
        curriculumId: "c-1",
      }),
    ).toBe("In the selected curriculum");
  });

  it("requires a professor for academic affairs", () => {
    expect(coursesScopeReady("academic_affairs", {})).toBe(false);
    expect(coursesScopeReady("academic_affairs", { professorId: "p-1" })).toBe(
      true,
    );
    expect(coursesScopeMessage("academic_affairs")).toContain("professor");
  });

  it("shows every curriculum for the university president before filters", () => {
    expect(coursesScopeReady("senior_management", {}, "university")).toBe(true);
    expect(coursesScopeReady("senior_management", {})).toBe(true);
    expect(
      coursesCurriculumSubtitle("senior_management", {}, "university"),
    ).toBe("All curriculum in the university");
    expect(
      coursesCurriculumSubtitle(
        "senior_management",
        { sectorId: "sec-a" },
        "university",
      ),
    ).toBe("In the selected scope");
  });

  it("requires college and professor for a sector dean", () => {
    expect(
      coursesScopeReady("senior_management", { collegeId: "col-a" }, "sector"),
    ).toBe(false);
    expect(
      coursesScopeReady(
        "senior_management",
        { collegeId: "col-a", professorId: "p-1" },
        "sector",
      ),
    ).toBe(true);
    expect(coursesScopeMessage("senior_management")).toContain("college");
    expect(coursesCurriculumSubtitle("senior_management", {}, "sector")).toBe(
      "In this college and professor scope",
    );
  });
});
