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
  "course" | "enrolled" | "average" | "passRate" | "standing";

export type ComparisonRow = {
  course: string;
  enrolled?: number;
  average: number;
  passRate: number;
};

export function comparisonSortValue(
  row: ComparisonRow,
  key: ComparisonSortKey,
): string | number {
  if (key === "course") return row.course;
  if (key === "enrolled") return row.enrolled ?? 0;
  if (key === "average") return row.average;
  if (key === "passRate") return row.passRate;
  return courseStanding(row.passRate) === "on_track" ? 1 : 0;
}

export function sortComparisonRows<T extends ComparisonRow>(
  rows: T[],
  key: ComparisonSortKey,
  asc: boolean,
): T[] {
  return [...rows].sort((a, b) => {
    const av = comparisonSortValue(a, key);
    const bv = comparisonSortValue(b, key);
    const cmp =
      typeof av === "string" && typeof bv === "string"
        ? av.localeCompare(bv, undefined, {
            numeric: true,
            sensitivity: "base",
          })
        : Number(av) - Number(bv);
    return asc ? cmp : -cmp;
  });
}

export function toggleComparisonSort(
  currentKey: ComparisonSortKey,
  currentAsc: boolean,
  nextKey: ComparisonSortKey,
): { key: ComparisonSortKey; asc: boolean } {
  if (nextKey === currentKey) return { key: currentKey, asc: !currentAsc };
  return { key: nextKey, asc: nextKey === "course" };
}

/** University senior management sees every curriculum, then narrows with filters.
 *  A sector dean still picks a college and professor first. College staff need a professor.
 */
export function coursesScopeReady(
  role: string,
  filters: Pick<AnalyticsFilters, "collegeId" | "professorId">,
  scopeLevel?: string | null,
): boolean {
  if (role === "professor") return true;
  if (role === "senior_management" && scopeLevel !== "sector") return true;
  if (role === "program_director" || role === "academic_affairs") {
    return Boolean(filters.professorId);
  }
  return Boolean(filters.collegeId && filters.professorId);
}

export function coursesCurriculumSubtitle(
  role: string,
  filters: Pick<AnalyticsFilters, "sectorId" | "collegeId" | "professorId">,
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
  return "In this college and professor scope";
}

export function coursesScopeMessage(role: string): string {
  if (role === "program_director" || role === "academic_affairs") {
    return "Select a professor to view curriculum.";
  }
  return "Select a college and professor to view curriculum.";
}
