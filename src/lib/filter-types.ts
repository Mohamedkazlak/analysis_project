export interface AnalyticsFilters {
  sectorId?: string | undefined;
  collegeId?: string | undefined;
  curriculumId?: string | undefined;
  studentId?: string | undefined;
  professorId?: string | undefined;
  academicYearId?: string | undefined;
  termId?: string | undefined;
}

export interface FilterOption {
  id: string;
  name: string;
  parentId?: string | null;
}

export interface CurriculumOption {
  id: string;
  code: string;
  name: string;
  collegeId: string;
}

export interface StudentOption {
  id: string;
  name: string;
  collegeId?: string | null;
}

export interface FilterOptionsResponse {
  role: string;
  scopeLevel: string | null;
  scopeLabel: string;
  visible: string[];
  required: string[];
  sectors: FilterOption[];
  colleges: FilterOption[];
  curricula: CurriculumOption[];
  professors?: FilterOption[];
  students: StudentOption[];
  hasMoreStudents?: boolean;
  studentPageSize?: number;
  containsSynthetic?: boolean;
}

export const FILTER_SEARCH_KEYS = [
  "sectorId",
  "collegeId",
  "curriculumId",
  "studentId",
  "professorId",
  "academicYearId",
  "termId",
] as const satisfies ReadonlyArray<keyof AnalyticsFilters>;

export const FILTER_SEARCH_DEFAULTS: AnalyticsFilters = {
  sectorId: undefined,
  collegeId: undefined,
  curriculumId: undefined,
  studentId: undefined,
  professorId: undefined,
  academicYearId: undefined,
  termId: undefined,
};

function searchValue(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

/** Parse dashboard filter IDs from a route query string or search object. */
export function fromSearchParams(
  search: string | URLSearchParams | Record<string, unknown>,
): AnalyticsFilters {
  const read = (key: string): unknown => {
    if (typeof search === "string") {
      const query = search.startsWith("?") ? search.slice(1) : search;
      return new URLSearchParams(query).get(key);
    }
    if (search instanceof URLSearchParams) return search.get(key);
    return search[key];
  };
  const next: AnalyticsFilters = {};
  for (const key of FILTER_SEARCH_KEYS) {
    const value = searchValue(read(key));
    if (value) next[key] = value;
  }
  return next;
}

export function toSearchParams(filters: AnalyticsFilters): string {
  const params = new URLSearchParams();
  for (const key of FILTER_SEARCH_KEYS) {
    const value = filters[key];
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function applyFilterSearch(
  prev: Record<string, unknown> | AnalyticsFilters,
  filters: AnalyticsFilters,
): AnalyticsFilters {
  const next: AnalyticsFilters = { ...prev };
  for (const key of FILTER_SEARCH_KEYS) {
    next[key] = filters[key];
  }
  return next;
}

export function sameFilters(a: AnalyticsFilters, b: AnalyticsFilters): boolean {
  return FILTER_SEARCH_KEYS.every((key) => a[key] === b[key]);
}

export function hasFilterValues(filters: AnalyticsFilters): boolean {
  return FILTER_SEARCH_KEYS.some((key) => Boolean(filters[key]));
}

export function filterQueryKey(
  resource: string,
  userId: string,
  filters: AnalyticsFilters,
): unknown[] {
  return [
    resource,
    userId,
    filters.sectorId ?? null,
    filters.collegeId ?? null,
    filters.curriculumId ?? null,
    filters.studentId ?? null,
    filters.professorId ?? null,
  ];
}

export function emptyFilters(): AnalyticsFilters {
  return {};
}

export function defaultVisible(
  role: string,
  scopeLevel?: string | null,
): string[] {
  if (role === "professor") return ["curriculum", "student"];
  if (role === "program_director" || role === "academic_affairs")
    return ["curriculum", "professor", "student"];
  if (role === "student") return [];
  if (role === "it_academic_integrity")
    return ["sector", "college", "curriculum"];
  if (role === "senior_management" && scopeLevel === "sector")
    return ["college", "professor"];
  if (role === "senior_management") return ["sector", "college", "professor"];
  return ["sector", "college", "curriculum", "student"];
}

const HIDDEN_FILTER_KEYS: Record<string, keyof AnalyticsFilters> = {
  sector: "sectorId",
  college: "collegeId",
  curriculum: "curriculumId",
  student: "studentId",
  professor: "professorId",
};

/** Drop stored filter values the current role is not allowed to set in the UI. */
export function sanitizeFilters(
  filters: AnalyticsFilters,
  visible: string[],
): AnalyticsFilters {
  const allowed = new Set(visible);
  const next: AnalyticsFilters = {};
  for (const [flag, key] of Object.entries(HIDDEN_FILTER_KEYS)) {
    if (allowed.has(flag) && filters[key]) {
      next[key] = filters[key];
    }
  }
  return next;
}

/** Parent changes drop invalid descendants: sector → college → professor/curriculum → student. */
export function setFilterSector(sectorId: string): AnalyticsFilters {
  return sectorId ? { sectorId } : emptyFilters();
}

export function setFilterCollege(
  current: AnalyticsFilters,
  collegeId: string,
  collegeSectorId?: string,
): AnalyticsFilters {
  const next: AnalyticsFilters = {};
  if (collegeId) {
    next.collegeId = collegeId;
    const sectorId = collegeSectorId || current.sectorId;
    if (sectorId) next.sectorId = sectorId;
    return next;
  }
  if (current.sectorId) next.sectorId = current.sectorId;
  return next;
}

export function setFilterProfessor(
  current: AnalyticsFilters,
  professorId: string,
): AnalyticsFilters {
  const next: AnalyticsFilters = {};
  if (current.sectorId) next.sectorId = current.sectorId;
  if (current.collegeId) next.collegeId = current.collegeId;
  if (professorId) next.professorId = professorId;
  return next;
}

export function setFilterCurriculum(
  current: AnalyticsFilters,
  curriculumId: string,
): AnalyticsFilters {
  const next: AnalyticsFilters = {};
  if (current.sectorId) next.sectorId = current.sectorId;
  if (current.collegeId) next.collegeId = current.collegeId;
  if (current.professorId) next.professorId = current.professorId;
  if (curriculumId) next.curriculumId = curriculumId;
  return next;
}

export function setFilterStudent(
  current: AnalyticsFilters,
  studentId: string,
): AnalyticsFilters {
  const next: AnalyticsFilters = {};
  if (current.sectorId) next.sectorId = current.sectorId;
  if (current.collegeId) next.collegeId = current.collegeId;
  if (current.professorId) next.professorId = current.professorId;
  if (current.curriculumId) next.curriculumId = current.curriculumId;
  if (studentId) next.studentId = studentId;
  return next;
}
