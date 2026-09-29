import { useRole } from "../role-context";
import { useAnalyticsFilters } from "./use-analytics-filters";

export function ScopeBanner() {
  const { role, viewer } = useRole();
  const { options, filters } = useAnalyticsFilters();
  if (role === "senior_management") return null;
  const sector = options?.sectors.find((s) => s.id === filters.sectorId)?.name;
  const college = options?.colleges.find(
    (c) => c.id === filters.collegeId,
  )?.name;
  const professor = options?.professors?.find(
    (p) => p.id === filters.professorId,
  )?.name;
  const curriculum = options?.curricula.find(
    (c) => c.id === filters.curriculumId,
  );
  const parts = [
    viewer.label,
    sector,
    college,
    professor,
    curriculum ? `${curriculum.code}` : null,
  ].filter(Boolean);
  return (
    <div className="rounded-2xl border border-iris/20 bg-iris/8 px-4 py-2.5 text-[12px] font-medium text-iris">
      Viewing · {parts.join(" · ")}
    </div>
  );
}
