import { useLayoutEffect } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import {
  ROLE_SLUG,
  getActiveDemoRole,
  roleRouteTo,
} from "@/lib/auth/role-guards";
import { loginPath, readStoredLocale } from "@/lib/i18n/locale-path";

export function LegacyRedirect({ leaf }: { leaf: string }) {
  const navigate = useNavigate();

  useLayoutEffect(() => {
    const locale = readStoredLocale();
    const role = getActiveDemoRole();
    if (!role) {
      window.location.href = loginPath(locale);
      return;
    }
    void navigate({
      to: roleRouteTo(leaf),
      params: { locale, role: ROLE_SLUG[role] },
      search: {},
      replace: true,
    });
  }, [leaf, navigate]);

  return null;
}

export function LegacyStudentRedirect() {
  const navigate = useNavigate();
  const { studentId } = useParams({ strict: false });

  useLayoutEffect(() => {
    const locale = readStoredLocale();
    const role = getActiveDemoRole();
    if (!role) {
      window.location.href = loginPath(locale);
      return;
    }
    if (!studentId) return;
    void navigate({
      to: "/$locale/$role/students/$studentId",
      params: { locale, role: ROLE_SLUG[role], studentId },
      search: {},
      replace: true,
    });
  }, [navigate, studentId]);

  return null;
}
