import { createFileRoute, redirect } from "@tanstack/react-router";
import { LegacyStudentRedirect } from "@/components/legacy-redirect";
import { ROLE_SLUG, ensureActiveRole } from "@/lib/auth/role-guards";
import { readStoredLocale } from "@/lib/i18n/locale-path";

export const Route = createFileRoute("/students/$studentId")({
  beforeLoad: async ({ params }) => {
    if (typeof window === "undefined") return;
    const locale = readStoredLocale();
    const role = await ensureActiveRole();
    if (!role) {
      throw redirect({
        to: "/$locale/login",
        params: { locale },
      });
    }
    throw redirect({
      to: "/$locale/$role/students/$studentId",
      params: {
        locale,
        role: ROLE_SLUG[role],
        studentId: params.studentId,
      },
      search: {},
    });
  },
  component: LegacyStudentRedirect,
});
