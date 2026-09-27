import { redirect } from "@tanstack/react-router";
import type { Role } from "../types";
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

export function roleHome(role: Role): string {
  return `/${ROLE_SLUG[role]}`;
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
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] && SLUG_ROLE[parts[0]]) {
    const rest = parts.slice(1).join("/");
    return rest ? `/${rest}` : "/";
  }
  return pathname || "/";
}

/** Map a backend/legacy leaf such as /courses onto /$role/courses. */
export function roleHref(role: Role, leaf: string): string {
  if (!leaf || leaf === "/" || HOME_LEAVES.has(leaf)) return roleHome(role);
  return `${roleHome(role)}${leaf.startsWith("/") ? leaf : `/${leaf}`}`;
}

export type RoleFileRoute =
  | "/$role"
  | "/$role/courses"
  | "/$role/exam-activity"
  | "/$role/performance"
  | "/$role/students"
  | "/$role/students/$studentId"
  | "/$role/participation"
  | "/$role/item-analysis"
  | "/$role/integrity"
  | "/$role/real-time";

/** TanStack `to` path for a report leaf under /$role. */
export function roleRouteTo(leaf: string): RoleFileRoute {
  if (!leaf || leaf === "/" || HOME_LEAVES.has(leaf)) return "/$role";
  return `/$role${leaf.startsWith("/") ? leaf : `/${leaf}`}` as RoleFileRoute;
}

export function roleNavigateTarget(dest: string): {
  to: RoleFileRoute;
  params: { role: string; studentId?: string };
} {
  const parts = dest.split("/").filter(Boolean);
  const slug = parts[0] ?? ROLE_SLUG.senior_management;
  const second = parts[1];
  const third = parts[2];
  if (!second) return { to: "/$role", params: { role: slug } };
  if (second === "students" && third) {
    return {
      to: "/$role/students/$studentId",
      params: { role: slug, studentId: third },
    };
  }
  return {
    to: `/$role/${second}` as RoleFileRoute,
    params: { role: slug },
  };
}

/** Client-only guard for leftover unprefixed report URLs. */
export function legacyLeafGuard(leaf: string) {
  return async () => {
    if (typeof window === "undefined") return;
    const role = await ensureActiveRole();
    if (!role) {
      throw redirect({ to: "/login" });
    }
    throw redirect({
      to: roleRouteTo(leaf),
      params: { role: ROLE_SLUG[role] },
      search: {},
    });
  };
}

export function legacyRedirectTo(pathname: string, role: Role): string | null {
  const parts = pathname.split("/").filter(Boolean);
  const first = parts[0];
  if (!first) return roleHome(role);
  if (SLUG_ROLE[first]) return null;
  const rest = parts.slice(1);
  if (first === "management" || first === "my-progress") {
    return rest.length ? `${roleHome(role)}/${rest.join("/")}` : roleHome(role);
  }
  if (LEGACY_REPORTS.has(first)) {
    return `${roleHome(role)}/${parts.join("/")}`;
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

export function assertRoleAccess(pathname: string, role: Role | null) {
  if (!role) {
    throw redirect({ to: "/login" });
  }

  const allowed = rolesAllowedForPath(pathname);
  if (!allowed) return;
  if (!allowed.includes(role)) {
    throw redirect({ to: roleHome(role) });
  }
}

/** Factory for route beforeLoad guards. `report` is the leaf, e.g. /courses. */
export function roleGuard(report: string) {
  return async () => {
    if (typeof window === "undefined") return;
    assertRoleAccess(report, await ensureActiveRole());
  };
}
