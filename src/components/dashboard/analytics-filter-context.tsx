import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { getFilterOptions } from "@/lib/api";
import {
  applyFilterSearch,
  defaultVisible,
  emptyFilters,
  fromSearchParams,
  hasFilterValues,
  sameFilters,
  sanitizeFilters,
  setFilterCollege,
  setFilterCurriculum,
  setFilterProfessor,
  setFilterSector,
  setFilterStudent,
  type AnalyticsFilters,
  type FilterOptionsResponse,
} from "@/lib/filter-types";
import { useRole } from "@/components/role-context";

interface AnalyticsFilterContextValue {
  filters: AnalyticsFilters;
  options: FilterOptionsResponse | undefined;
  setSectorId: (id: string) => void;
  setCollegeId: (id: string) => void;
  setCurriculumId: (id: string) => void;
  setProfessorId: (id: string) => void;
  setStudentId: (id: string) => void;
  studentQuery: string;
  setStudentQuery: (q: string) => void;
  clear: () => void;
  filtersReady: boolean;
}

const AnalyticsFilterContext =
  createContext<AnalyticsFilterContextValue | null>(null);

function writeStored(userId: string, filters: AnalyticsFilters) {
  if (typeof window === "undefined" || !userId) return;
  sessionStorage.setItem(
    `bnu.analyticsFilters.${userId}`,
    JSON.stringify(filters),
  );
}

export function AnalyticsFilterProvider({ children }: { children: ReactNode }) {
  const { user, role, viewer } = useRole();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const searchStr = useRouterState({
    select: (s) => s.location.searchStr ?? "",
  });
  const [filters, setFilters] = useState<AnalyticsFilters>(() => {
    const visible = defaultVisible(role, viewer.level);
    return sanitizeFilters(fromSearchParams(searchStr), visible);
  });
  const [studentQuery, setStudentQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const lastPathname = useRef(pathname);

  const persist = useCallback(
    (next: AnalyticsFilters) => {
      setFilters(next);
      writeStored(user.id, next);
      if (
        pathname === "/login" ||
        pathname === "/en/login" ||
        pathname === "/ar/login"
      ) {
        return;
      }
      void navigate({
        to: ".",
        replace: true,
        resetScroll: false,
        search: (prev) => applyFilterSearch(prev, next),
      });
    },
    [navigate, pathname, user.id],
  );

  useEffect(() => {
    const visible = defaultVisible(role, viewer.level);
    setFilters(sanitizeFilters(fromSearchParams(searchStr), visible));
    // URL is read at user switch time; address-bar edits are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.id]);

  useEffect(() => {
    const fromUrl = fromSearchParams(searchStr);
    setFilters((current) => {
      if (sameFilters(current, fromUrl)) return current;
      writeStored(user.id, fromUrl);
      return fromUrl;
    });
  }, [searchStr, user.id]);

  useEffect(() => {
    if (lastPathname.current === pathname) return;
    lastPathname.current = pathname;
    setStudentQuery("");
    setDebouncedQuery("");
    const fromUrl = fromSearchParams(searchStr);
    if (hasFilterValues(fromUrl)) return;
    const cleared = emptyFilters();
    setFilters(cleared);
    writeStored(user.id, cleared);
  }, [pathname, searchStr, user.id]);

  useEffect(() => {
    const handle = window.setTimeout(
      () => setDebouncedQuery(studentQuery.trim()),
      250,
    );
    return () => window.clearTimeout(handle);
  }, [studentQuery]);

  const optionsQuery = useQuery({
    queryKey: [
      "filter-options",
      user.id,
      filters.sectorId ?? null,
      filters.collegeId ?? null,
      filters.curriculumId ?? null,
      filters.professorId ?? null,
      debouncedQuery,
    ],
    queryFn: () => getFilterOptions(filters, debouncedQuery || undefined),
    enabled: Boolean(user.id) && role !== "student",
  });
  const options = optionsQuery.data;

  useEffect(() => {
    const visible = defaultVisible(role, viewer.level);
    const next = sanitizeFilters(filters, visible);
    if (!sameFilters(filters, next)) persist(next);
  }, [filters, persist, role, viewer.level]);

  const setSectorId = useCallback(
    (id: string) => {
      persist(setFilterSector(id));
    },
    [persist],
  );
  const setCollegeId = useCallback(
    (id: string) => {
      const collegeSectorId = options?.colleges.find(
        (c) => c.id === id,
      )?.parentId;
      persist(setFilterCollege(filters, id, collegeSectorId ?? undefined));
    },
    [persist, filters, options],
  );
  const setProfessorId = useCallback(
    (id: string) => {
      persist(setFilterProfessor(filters, id));
    },
    [persist, filters],
  );
  const setCurriculumId = useCallback(
    (id: string) => {
      persist(setFilterCurriculum(filters, id));
    },
    [persist, filters],
  );
  const setStudentId = useCallback(
    (id: string) => {
      persist(setFilterStudent(filters, id));
    },
    [persist, filters],
  );
  const clear = useCallback(() => persist(emptyFilters()), [persist]);

  const required = options?.required ?? [];
  const filtersReady =
    role === "student" ||
    required.every((key) => {
      if (key === "sectorId") return Boolean(filters.sectorId);
      if (key === "collegeId") return Boolean(filters.collegeId);
      return true;
    });

  const value = useMemo(
    () => ({
      filters,
      options,
      setSectorId,
      setCollegeId,
      setCurriculumId,
      setProfessorId,
      setStudentId,
      studentQuery,
      setStudentQuery,
      clear,
      filtersReady,
    }),
    [
      filters,
      options,
      setSectorId,
      setCollegeId,
      setCurriculumId,
      setProfessorId,
      setStudentId,
      studentQuery,
      setStudentQuery,
      clear,
      filtersReady,
    ],
  );

  return (
    <AnalyticsFilterContext.Provider value={value}>
      {children}
    </AnalyticsFilterContext.Provider>
  );
}

export function useAnalyticsFilterContext() {
  const ctx = useContext(AnalyticsFilterContext);
  if (!ctx) {
    throw new Error(
      "useAnalyticsFilterContext must be used within AnalyticsFilterProvider",
    );
  }
  return ctx;
}
