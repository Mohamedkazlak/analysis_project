import type {
  CoursePerformanceReport,
  IntegrityReport,
  ItemAnalysisReport,
  ManagementOverview,
  ParticipationReport,
  RealTimeReport,
  StudentDashboardReport,
  StudentDirectoryRow,
  StudentPerformanceReport,
  StudentProfileReport,
} from "./types";
import { getAuthToken, clearAuthToken } from "./auth/token";
import {
  toSearchParams,
  type AnalyticsFilters,
  type FilterOptionsResponse,
} from "./filter-types";
import { isLoginPath, loginPath, readStoredLocale } from "./i18n/locale-path";

export const BACKEND_URL: string =
  import.meta.env["VITE_BACKEND_URL"] ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function fetchFromBackend<T>(
  endpoint: string,
  init?: {
    method?: "GET" | "POST";
    body?: unknown;
    timeoutMs?: number;
    signal?: AbortSignal;
  },
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (init?.body !== undefined) headers["Content-Type"] = "application/json";

  const controller = new AbortController();
  const timeout = init?.timeoutMs
    ? setTimeout(() => controller.abort(), init.timeoutMs)
    : undefined;
  const onAbort = () => controller.abort();
  init?.signal?.addEventListener("abort", onAbort);

  try {
    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      method: init?.method ?? "GET",
      headers,
      ...(init?.body !== undefined ? { body: JSON.stringify(init.body) } : {}),
      signal: controller.signal,
    });
    if (response.status === 401) {
      clearAuthToken();
      if (
        typeof window !== "undefined" &&
        !isLoginPath(window.location.pathname)
      ) {
        window.location.href = loginPath(readStoredLocale());
      }
      throw new ApiError("Unauthorized", 401);
    }
    if (response.status === 403) {
      throw new ApiError("Access Denied", 403);
    }
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const payload = (await response.json()) as { detail?: unknown };
        if (typeof payload.detail === "string" && payload.detail.trim()) {
          detail = payload.detail.trim();
        }
      } catch {
        // ignore non-JSON error bodies
      }
      throw new ApiError(detail, response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("Request timed out", 408);
    }
    throw error;
  } finally {
    if (timeout) clearTimeout(timeout);
    init?.signal?.removeEventListener("abort", onAbort);
  }
}

export function getManagementOverview(
  filters: AnalyticsFilters = {},
  language: "en" | "ar" = "en",
) {
  const base = toSearchParams(filters);
  const sep = base.includes("?") ? "&" : "?";
  return fetchFromBackend<ManagementOverview>(
    `/api/management-overview${base}${sep}language=${language}`,
  );
}

export function getStudentPerformance(filters: AnalyticsFilters = {}) {
  return fetchFromBackend<StudentPerformanceReport>(
    `/api/student-performance${toSearchParams(filters)}`,
  );
}

export function getItemAnalysis(
  filters: AnalyticsFilters = {},
  language: "en" | "ar" = "en",
) {
  const base = toSearchParams(filters);
  const sep = base.includes("?") ? "&" : "?";
  return fetchFromBackend<ItemAnalysisReport>(
    `/api/item-analysis${base}${sep}language=${language}`,
  );
}

export function getIntegrityReport(
  filters: AnalyticsFilters = {},
  language: "en" | "ar" = "en",
) {
  const base = toSearchParams(filters);
  const sep = base.includes("?") ? "&" : "?";
  return fetchFromBackend<IntegrityReport>(
    `/api/integrity-report${base}${sep}language=${language}`,
  );
}

export function getParticipationReport(
  filters: AnalyticsFilters = {},
  language: "en" | "ar" = "en",
) {
  const base = toSearchParams(filters);
  const sep = base.includes("?") ? "&" : "?";
  return fetchFromBackend<ParticipationReport>(
    `/api/participation-report${base}${sep}language=${language}`,
  );
}

export function getCoursePerformance(filters: AnalyticsFilters = {}) {
  return fetchFromBackend<CoursePerformanceReport>(
    `/api/course-performance${toSearchParams(filters)}`,
  );
}

export function getRealTimeStruggling(
  filters: AnalyticsFilters = {},
  language: "en" | "ar" = "en",
) {
  const base = toSearchParams(filters);
  const sep = base.includes("?") ? "&" : "?";
  return fetchFromBackend<RealTimeReport>(
    `/api/real-time-struggling${base}${sep}language=${language}`,
  );
}

export function getStudentDashboard(filters: AnalyticsFilters = {}) {
  return fetchFromBackend<StudentDashboardReport>(
    `/api/student-dashboard${toSearchParams(filters)}`,
  );
}

export function getStudentDirectory(filters: AnalyticsFilters = {}) {
  return fetchFromBackend<StudentDirectoryRow[]>(
    `/api/student-directory${toSearchParams(filters)}`,
  );
}

export function getStudentProfile(
  studentId: string,
  filters: AnalyticsFilters = {},
) {
  return fetchFromBackend<StudentProfileReport>(
    `/api/students/${studentId}${toSearchParams(filters)}`,
  );
}

export function getFilterOptions(filters: AnalyticsFilters = {}, q?: string) {
  const params = new URLSearchParams(
    toSearchParams(filters).replace(/^\?/, ""),
  );
  if (q) params.set("q", q);
  const query = params.toString();
  return fetchFromBackend<FilterOptionsResponse>(
    `/api/filter-options${query ? `?${query}` : ""}`,
  );
}

export interface MeResponse {
  user_id: string;
  role: string;
  scope_id: string | null;
  person_id: string;
  student_id?: string | null;
  name?: string | null;
  title?: string | null;
  display_role?: string | null;
  scope_level?: string | null;
  sector_id?: string | null;
  college_id?: string | null;
  sector_name?: string | null;
  college_name?: string | null;
  university_name?: string | null;
  scope_label?: string | null;
  course_ids?: string[];
  initials?: string | null;
  courses?: {
    id: string;
    code: string;
    name: string;
    enrolled: number;
    sections: string[];
  }[];
}

export function getMe() {
  return fetchFromBackend<MeResponse>("/auth/me");
}
