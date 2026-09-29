import type { AnalyticsFilters } from "@/lib/filter-types";

export type CourseStanding = "on_track" | "needs_support";
export type StandingFilter = "all" | CourseStanding;

export const ON_TRACK_PASS_RATE = 75;

export function courseStanding(passRate: number): CourseStanding {
  return passRate >= ON_TRACK_PASS_RATE ? "on_track" : "needs_support";
}

export function courseStandingLabel(standing: CourseStanding): string {
  return standing === "on_track" ? "On track" : "Needs support";
}

export function filterByStanding<T extends { passRate: number }>(
  rows: T[],
  standing: StandingFilter,
): T[] {
  if (standing === "all") return rows;
  return rows.filter((row) => courseStanding(row.passRate) === standing);
}

export type ComparisonSortKey =
  "college" | "course" | "enrolled" | "average" | "passRate" | "standing";

export type ComparisonRow = {
  college?: string;
  course: string;
  enrolled?: number;
  average: number;
  passRate: number;
};

export function comparisonSortValue(
  row: ComparisonRow,
  key: ComparisonSortKey,
): string | number {
  if (key === "college") return row.college ?? "";
  if (key === "course") return row.course;
  if (key === "enrolled") return row.enrolled ?? 0;
  if (key === "average") return row.average;
  if (key === "passRate") return row.passRate;
  return courseStanding(row.passRate) === "on_track" ? 1 : 0;
}

function compareSortValues(av: string | number, bv: string | number): number {
  if (typeof av === "string" && typeof bv === "string") {
    return av.localeCompare(bv, undefined, {
      numeric: true,
      sensitivity: "base",
    });
  }
  return Number(av) - Number(bv);
}

/** Stable column sort with readable tie-breakers (college → course). */
export function sortComparisonRows<T extends ComparisonRow>(
  rows: T[],
  key: ComparisonSortKey,
  asc: boolean,
): T[] {
  return [...rows].sort((a, b) => {
    const primary = compareSortValues(
      comparisonSortValue(a, key),
      comparisonSortValue(b, key),
    );
    if (primary !== 0) return asc ? primary : -primary;

    if (key !== "college") {
      const byCollege = compareSortValues(
        comparisonSortValue(a, "college"),
        comparisonSortValue(b, "college"),
      );
      if (byCollege !== 0) return byCollege;
    }

    return compareSortValues(
      comparisonSortValue(a, "course"),
      comparisonSortValue(b, "course"),
    );
  });
}

export function toggleComparisonSort(
  currentKey: ComparisonSortKey,
  currentAsc: boolean,
  nextKey: ComparisonSortKey,
): { key: ComparisonSortKey; asc: boolean } {
  if (nextKey === currentKey) return { key: currentKey, asc: !currentAsc };
  return {
    key: nextKey,
    asc: nextKey === "course" || nextKey === "college",
  };
}

/** University senior management sees every curriculum, then narrows with filters.
 *  Program directors see their whole college until they narrow further.
 *  A sector dean still picks a college and professor first. Academic affairs need a professor.
 */
export function coursesScopeReady(
  role: string,
  filters: Pick<AnalyticsFilters, "collegeId" | "professorId">,
  scopeLevel?: string | null,
): boolean {
  if (role === "professor" || role === "program_director") return true;
  if (role === "senior_management" && scopeLevel !== "sector") return true;
  if (role === "academic_affairs") {
    return Boolean(filters.professorId);
  }
  return Boolean(filters.collegeId && filters.professorId);
}

export function coursesCurriculumSubtitle(
  role: string,
  filters: Pick<
    AnalyticsFilters,
    "sectorId" | "collegeId" | "professorId" | "curriculumId"
  >,
  scopeLevel?: string | null,
): string {
  if (role === "senior_management" && scopeLevel !== "sector") {
    const narrowed = Boolean(
      filters.sectorId || filters.collegeId || filters.professorId,
    );
    return narrowed
      ? "In the selected scope"
      : "All curriculum in the university";
  }
  if (role === "program_director") {
    if (filters.curriculumId) return "In the selected curriculum";
    if (filters.professorId) return "In the selected professor scope";
    return "All curriculum in this college";
  }
  return "In this college and professor scope";
}

export function coursesScopeMessage(role: string): string {
  if (role === "academic_affairs") {
    return "Select a professor to view curriculum.";
  }
  return "Select a college and professor to view curriculum.";
}
