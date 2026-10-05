import { createFileRoute } from "@tanstack/react-router";
import { OverviewDashboard } from "@/components/dashboard/overview-dashboard";
import { AcademicAffairsPage } from "@/components/pages/academic-affairs-page";
import { MyProgressPage } from "@/components/pages/my-progress-page";
import { ProfessorPage } from "@/components/pages/professor-page";
import { IntegrityPage } from "@/components/pages/integrity-page";
import { roleGuard } from "@/lib/auth/role-guards";
import { useRole } from "@/components/role-context";

export const Route = createFileRoute("/$locale/$role/")({
  beforeLoad: roleGuard("/"),
  head: () => ({
    meta: [
      { title: "BNU — AI-driven Dashboard" },
      {
        name: "description",
        content: "Role-scoped assessment reporting and analytics.",
      },
    ],
  }),
  component: RoleHome,
});

function RoleHome() {
  const { role, affiliation } = useRole();
  if (role === "senior_management") {
    return (
      <OverviewDashboard
        role="senior_management"
        scopeLabel={affiliation.label}
      />
    );
  }
  if (role === "program_director") {
    return (
      <OverviewDashboard
        role="program_director"
        scopeLabel={affiliation.label}
      />
    );
  }
  if (role === "academic_affairs") return <AcademicAffairsPage />;
  if (role === "professor") return <ProfessorPage />;
  if (role === "it_academic_integrity") return <IntegrityPage />;
  return <MyProgressPage />;
}
