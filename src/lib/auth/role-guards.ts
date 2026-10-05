import { redirect } from "@tanstack/react-router";
import type { Role } from "../types";
import type { Locale } from "../i18n/types";
import {
  isLocale,
  localeFromPathname,
  loginPath,
  readStoredLocale,
  stripLocalePrefix,
  withLocalePrefix,
} from "../i18n/locale-path";
import { getMe } from "../api";
import {
  getAuthToken,
  rememberSessionRole,
  roleFromToken,
  sessionRoleForToken,
  userIdFromToken,
} from "./token";

export const ROLE_SLUG: Record<Role, string> = {
  senior_management: "senior-management",
  program_director: "program-director",
  academic_affairs: "academic-affairs",
  professor: "professor",
  it_academic_integrity: "academic-integrity",
  student: "student",
};

export const SLUG_ROLE: Record<string, Role> = {
  "senior-management": "senior_management",
  "program-director": "program_director",
  "academic-affairs": "academic_affairs",
  professor: "professor",
  "academic-integrity": "it_academic_integrity",
  student: "student",
};

const HOME_LEAVES = new Set([
  "/management",
  "/program-director",
  "/academic-affairs",
  "/professor",
  "/my-progress",
]);

const LEGACY_REPORTS = new Set([
  "management",
  "my-progress",
  "courses",
  "exam-activity",
  "performance",
  "students",
  "participation",
  "item-analysis",
  "integrity",
  "real-time",
]);

export function roleSlug(role: Role): string {
  return ROLE_SLUG[role];
}

export function roleHome(
  role: Role,
  locale: Locale = readStoredLocale(),
): string {
  return `/${locale}/${ROLE_SLUG[role]}`;
}

export const roleRoutes: Record<Role, string> = {
  senior_management: roleHome("senior_management"),
  program_director: roleHome("program_director"),
  academic_affairs: roleHome("academic_affairs"),
  professor: roleHome("professor"),
  it_academic_integrity: roleHome("it_academic_integrity"),
  student: roleHome("student"),
};

export function reportPath(pathname: string): string {
  const parts = stripLocalePrefix(pathname).split("/").filter(Boolean);
  if (parts[0] && SLUG_ROLE[parts[0]]) {
    const rest = parts.slice(1).join("/");
    return rest ? `/${rest}` : "/";
  }
  return stripLocalePrefix(pathname) || "/";
}

/** Map a backend/legacy leaf such as /courses onto /{locale}/{role}/courses. */
export function roleHref(
  role: Role,
  leaf: string,
  locale: Locale = readStoredLocale(),
): string {
  if (!leaf || leaf === "/" || HOME_LEAVES.has(leaf)) {
    return roleHome(role, locale);
  }
  return `${roleHome(role, locale)}${leaf.startsWith("/") ? leaf : `/${leaf}`}`;
}

export type RoleFileRoute =
  | "/$locale/$role"
  | "/$locale/$role/courses"
  | "/$locale/$role/exam-activity"
  | "/$locale/$role/performance"
  | "/$locale/$role/students"
  | "/$locale/$role/students/$studentId"
  | "/$locale/$role/participation"
  | "/$locale/$role/item-analysis"
  | "/$locale/$role/integrity"
  | "/$locale/$role/real-time";

/** TanStack `to` path for a report leaf under /$locale/$role. */
export function roleRouteTo(leaf: string): RoleFileRoute {
  if (!leaf || leaf === "/" || HOME_LEAVES.has(leaf)) return "/$locale/$role";
  return `/$locale/$role${leaf.startsWith("/") ? leaf : `/${leaf}`}` as RoleFileRoute;
}

export function roleNavigateTarget(
  dest: string,
  locale?: Locale,
): {
  to: RoleFileRoute;
  params: { locale: Locale; role: string; studentId?: string };
} {
  const loc = locale ?? localeFromPathname(dest) ?? readStoredLocale();
  const parts = stripLocalePrefix(dest).split("/").filter(Boolean);
  const slug = parts[0] ?? ROLE_SLUG.senior_management;
  const second = parts[1];
  const third = parts[2];
  if (!second) {
    return { to: "/$locale/$role", params: { locale: loc, role: slug } };
  }
  if (second === "students" && third) {
    return {
      to: "/$locale/$role/students/$studentId",
      params: { locale: loc, role: slug, studentId: third },
    };
  }
  return {
    to: `/$locale/$role/${second}` as RoleFileRoute,
    params: { locale: loc, role: slug },
  };
}

/** Client-only guard for leftover unprefixed report URLs. */
export function legacyLeafGuard(leaf: string) {
  return async () => {
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
      to: roleRouteTo(leaf),
      params: { locale, role: ROLE_SLUG[role] },
      search: {},
    });
  };
}

/**
 * Rewrite unprefixed or legacy URLs onto /{locale}/{role}/….
 * Returns null when the path is already a localized role URL.
 */
export function legacyRedirectTo(
  pathname: string,
  role: Role,
  locale?: Locale,
): string | null {
  const parts = pathname.split("/").filter(Boolean);
  const loc = locale ?? localeFromPathname(pathname) ?? readStoredLocale();

  if (parts[0] === "login" || (isLocale(parts[0]) && parts[1] === "login")) {
    return null;
  }

  // Already /{locale}/{role}/…
  if (isLocale(parts[0]) && parts[1] && SLUG_ROLE[parts[1]]) {
    return null;
  }

  // Unprefixed role URL: /senior-management/courses
  if (parts[0] && SLUG_ROLE[parts[0]]) {
    return withLocalePrefix(pathname, loc);
  }

  const bareParts = isLocale(parts[0]) ? parts.slice(1) : parts;
  const first = bareParts[0];
  if (!first) return roleHome(role, loc);

  if (first === "management" || first === "my-progress") {
    const rest = bareParts.slice(1);
    return rest.length
      ? `${roleHome(role, loc)}/${rest.join("/")}`
      : roleHome(role, loc);
  }
  if (LEGACY_REPORTS.has(first)) {
    return `${roleHome(role, loc)}/${bareParts.join("/")}`;
  }
  return null;
}

/** Role used to choose a dashboard. Comes from the last live account lookup. */
export function getActiveDemoRole(): Role | null {
  const token = getAuthToken();
  return sessionRoleForToken(token) ?? roleFromToken(token);
}

/** Load the live role when the browser has a token but no dashboard hint yet. */
export async function ensureActiveRole(): Promise<Role | null> {
  const token = getAuthToken();
  const userId = userIdFromToken(token);
  if (!userId) return null;
  const known = sessionRoleForToken(token) ?? roleFromToken(token);
  if (known) return known;
  try {
    const me = await getMe();
    if (!me?.user_id || me.user_id !== userId || !me.role) return null;
    rememberSessionRole(me.user_id, me.role);
    return getActiveDemoRole();
  } catch {
    return null;
  }
}

export function getActiveDemoUserId(): string | null {
  return userIdFromToken(getAuthToken());
}

/** Report paths each role may open. Homes are always included via "/". */
export const allowedRolesByPath: Record<string, Role[]> = {
  "/": [
    "senior_management",
    "program_director",
    "academic_affairs",
    "professor",
    "it_academic_integrity",
    "student",
  ],
  "/courses": [
    "senior_management",
    "program_director",
    "academic_affairs",
    "professor",
  ],
  "/exam-activity": [
    "senior_management",
    "program_director",
    "academic_affairs",
  ],
  "/performance": [
    "senior_management",
    "program_director",
    "academic_affairs",
    "professor",
  ],
  "/students": [
    "senior_management",
    "program_director",
    "academic_affairs",
    "professor",
  ],
  "/participation": [
    "senior_management",
    "program_director",
    "academic_affairs",
    "professor",
  ],
  "/item-analysis": [
    "senior_management",
    "program_director",
    "academic_affairs",
    "professor",
    "it_academic_integrity",
  ],
  "/integrity": ["it_academic_integrity", "senior_management"],
  "/real-time": ["senior_management", "professor", "it_academic_integrity"],
};

export function rolesAllowedForPath(pathname: string): Role[] | undefined {
  const report = reportPath(pathname);
  if (allowedRolesByPath[report]) return allowedRolesByPath[report];
  if (report.startsWith("/students/")) return allowedRolesByPath["/students"];
  return undefined;
}

export function assertRoleAccess(
  pathname: string,
  role: Role | null,
  locale: Locale = readStoredLocale(),
) {
  if (!role) {
    throw redirect({
      to: "/$locale/login",
      params: { locale },
    });
  }

  const allowed = rolesAllowedForPath(pathname);
  if (!allowed) return;
  if (!allowed.includes(role)) {
    throw redirect({
      to: "/$locale/$role",
      params: { locale, role: ROLE_SLUG[role] },
    });
  }
}

/** Factory for route beforeLoad guards. `report` is the leaf, e.g. /courses. */
export function roleGuard(report: string) {
  return async () => {
    if (typeof window === "undefined") return;
    assertRoleAccess(report, await ensureActiveRole(), readStoredLocale());
  };
}

export { loginPath, readStoredLocale };
