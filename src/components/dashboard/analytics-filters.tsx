import { FilterBar, Select } from "@/components/dashboard/dashboard-ui";
import { useAnalyticsFilters } from "@/components/dashboard/use-analytics-filters";
import { useRole } from "@/components/role-context";
import { defaultVisible } from "@/lib/filter-types";
import { useLocale, translateOrgName, translatePersonTitle } from "@/lib/i18n";

export function AnalyticsFilters() {
  const { role, viewer } = useRole();
  const { locale, messages } = useLocale();
  const f = messages.filters;
  const {
    filters,
    options,
    setSectorId,
    setCollegeId,
    setCurriculumId,
    setProfessorId,
    setStudentId,
    studentQuery,
    setStudentQuery,
    filtersReady,
  } = useAnalyticsFilters();

  if (role === "student") return null;

  const visible = options?.visible ?? defaultVisible(role, viewer.level);
  const required = options?.required ?? [];
  const showSector = visible.includes("sector");
  const showCollege = visible.includes("college");
  const showCurriculum = visible.includes("curriculum");
  const showProfessor = visible.includes("professor");
  const showStudent = visible.includes("student");

  const sectorOptions = [
    {
      value: "",
      label: required.includes("sectorId") ? f.selectSector : f.allSectors,
    },
    ...(options?.sectors ?? []).map((s) => ({
      value: s.id,
      label: translateOrgName(s.name, locale),
    })),
  ];
  const collegeOptions = [
    {
      value: "",
      label: required.includes("collegeId") ? f.selectCollege : f.allColleges,
    },
    ...(options?.colleges ?? []).map((s) => ({
      value: s.id,
      label: translateOrgName(s.name, locale),
    })),
  ];
  const professorOptions = [
    { value: "", label: f.allProfessors },
    ...(options?.professors ?? []).map((p) => ({
      value: p.id,
      label: translatePersonTitle(p.name, locale),
    })),
  ];
  const curriculumOptions = [
    { value: "", label: f.allCurriculum },
    ...(options?.curricula ?? []).map((c) => ({
      value: c.id,
      label: `${c.code} · ${c.name}`,
    })),
  ];
  const studentOptions = [
    { value: "", label: f.allStudents },
    ...(options?.students ?? []).map((s) => ({ value: s.id, label: s.name })),
  ];

  return (
    <div className="space-y-2">
      <FilterBar>
        {showSector ? (
          <Select
            label={f.sector}
            value={filters.sectorId ?? ""}
            options={sectorOptions}
            onChange={setSectorId}
          />
        ) : null}
        {showCollege ? (
          <Select
            label={f.college}
            value={filters.collegeId ?? ""}
            options={collegeOptions}
            onChange={setCollegeId}
          />
        ) : null}
        {showProfessor ? (
          <Select
            label={f.professor}
            value={filters.professorId ?? ""}
            options={professorOptions}
            onChange={setProfessorId}
          />
        ) : null}
        {showCurriculum ? (
          <Select
            label={f.curriculum}
            value={filters.curriculumId ?? ""}
            options={curriculumOptions}
            onChange={setCurriculumId}
          />
        ) : null}
        {showStudent ? (
          <>
            <Select
              label={f.student}
              value={filters.studentId ?? ""}
              options={studentOptions}
              onChange={setStudentId}
            />
            <label className="flex items-center gap-2 rounded-full border border-white/80 bg-white/70 px-3 py-1.5 backdrop-blur-xl">
              <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-soft">
                {f.search}
              </span>
              <input
                value={studentQuery}
                onChange={(e) => setStudentQuery(e.target.value)}
                placeholder={f.searchPlaceholder}
                className="w-28 bg-transparent text-[11px] font-semibold text-ink outline-none"
              />
            </label>
          </>
        ) : null}
      </FilterBar>
      {showStudent && options?.hasMoreStudents ? (
        <p className="text-[12px] text-ink-soft">
          {f.studentsCap.replace("{n}", String(options.studentPageSize ?? 150))}
        </p>
      ) : null}
      {!filtersReady ? (
        <p className="text-[12px] text-ink-soft">{f.required}</p>
      ) : null}
    </div>
  );
}

export function FiltersRequiredNotice({ message }: { message?: string }) {
  const { messages } = useLocale();
  return (
    <div className="rounded-2xl border border-iris/20 bg-iris/8 px-4 py-3 text-[13px] text-ink-soft">
      {message ?? messages.filters.required}
    </div>
  );
}
