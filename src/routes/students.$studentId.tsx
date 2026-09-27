import { createFileRoute, redirect } from "@tanstack/react-router";
import { LegacyStudentRedirect } from "@/components/legacy-redirect";
import { ROLE_SLUG, ensureActiveRole } from "@/lib/auth/role-guards";

export const Route = createFileRoute("/students/$studentId")({
  beforeLoad: async ({ params }) => {
    if (typeof window === "undefined") return;
    const role = await ensureActiveRole();
    if (!role) {
      throw redirect({ to: "/login" });
    }
    throw redirect({
      to: "/$role/students/$studentId",
      params: { role: ROLE_SLUG[role], studentId: params.studentId },
      search: {},
    });
  },
  component: LegacyStudentRedirect,
});
