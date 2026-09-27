import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import type { DemoUser, Role, UserAffiliation, ViewerScope } from "@/lib/types";
import { roleHome, ROLE_SLUG, SLUG_ROLE } from "@/lib/auth/role-guards";
import { useRouterState } from "@tanstack/react-router";
import {
  getAuthToken,
  rememberSessionRole,
  roleFromToken,
  scopeIdFromToken,
  sessionRoleForToken,
  studentIdFromToken,
  userIdFromToken,
} from "@/lib/auth/token";
import { getMe, type MeResponse } from "@/lib/api";

export interface NavItem {
  to: string;
  label: string;
  title: string;
}

export const roleLabels: Record<Role, string> = {
  senior_management: "Senior Management",
  program_director: "Program Director",
  academic_affairs: "Academic Affairs",
  professor: "Professor",
  it_academic_integrity: "Academic Integrity",
  student: "Student",
};

export const allRoles: Role[] = [
  "senior_management",
  "program_director",
  "academic_affairs",
  "professor",
  "it_academic_integrity",
  "student",
];

export const navByRole: Record<Role, { group: string; items: NavItem[] }[]> = {
  senior_management: [
    {
      group: "Overview",
      items: [
        {
          to: "/",
          label: "Institution Overview",
          title: "Senior Management Overview",
        },
        {
          to: "/exam-activity",
          label: "Exam Activity",
          title: "Exam Activity & Enrollment Trends",
        },
        {
          to: "/courses",
          label: "Curriculum Performance",
          title: "Curriculum & Instructor Performance",
        },
      ],
    },
    {
      group: "Academic reports",
      items: [
        {
          to: "/performance",
          label: "Student Performance",
          title: "Student Performance Reports",
        },
        {
          to: "/students",
          label: "Student Profiles",
          title: "Student Profiles & Academic History",
        },
        {
          to: "/participation",
          label: "Participation",
          title: "Student Participation Reports",
        },
        {
          to: "/item-analysis",
          label: "Item Analysis",
          title: "Item Analysis Reports",
        },
        {
          to: "/integrity",
          label: "Academic Integrity",
          title: "Academic Integrity & Exam Monitoring",
        },
        {
          to: "/real-time",
          label: "Live Exam Monitor",
          title: "Live Monitoring",
        },
      ],
    },
  ],
  program_director: [
    {
      group: "Overview",
      items: [
        {
          to: "/",
          label: "College Dashboard",
          title: "Program Director · College Dashboard",
        },
        {
          to: "/exam-activity",
          label: "Exam Activity",
          title: "Exam Activity & Enrollment Trends",
        },
        {
          to: "/courses",
          label: "Curriculum Performance",
          title: "Curriculum & Instructor Performance",
        },
      ],
    },
    {
      group: "Academic reports",
      items: [
        {
          to: "/performance",
          label: "Student Performance",
          title: "Student Performance Reports",
        },
        {
          to: "/students",
          label: "Student Profiles",
          title: "Student Profiles & Academic History",
        },
        {
          to: "/participation",
          label: "Participation",
          title: "Student Participation Reports",
        },
        {
          to: "/item-analysis",
          label: "Item Analysis",
          title: "Item Analysis Reports",
        },
      ],
    },
  ],
  academic_affairs: [
    {
      group: "College performance",
      items: [
        {
          to: "/",
          label: "College Dashboard",
          title: "Academic Affairs · Student Performance & Attendance",
        },
        {
          to: "/exam-activity",
          label: "Exam Activity",
          title: "Exam Activity & Enrollment Trends",
        },
        {
          to: "/performance",
          label: "Student Performance",
          title: "Student Performance Reports",
        },
        {
          to: "/participation",
          label: "Attendance",
          title: "Attendance & Participation Reports",
        },
        {
          to: "/courses",
          label: "Curricula",
          title: "Curriculum Performance",
        },
        {
          to: "/item-analysis",
          label: "Item Analysis",
          title: "Item Analysis Reports",
        },
        {
          to: "/students",
          label: "Student Profiles",
          title: "Student Profiles & Academic History",
        },
      ],
    },
  ],
  professor: [
    {
      group: "My courses",
      items: [
        {
          to: "/",
          label: "Course Home",
          title: "Professor Course Dashboard",
        },
        {
          to: "/courses",
          label: "My Curricula",
          title: "Curriculum Performance",
        },
        {
          to: "/performance",
          label: "Student Performance",
          title: "Student Performance Reports",
        },
        {
          to: "/students",
          label: "Student Profiles",
          title: "Student Profiles & Academic History",
        },
        {
          to: "/item-analysis",
          label: "Item Analysis",
          title: "Item Analysis Reports",
        },
        {
          to: "/participation",
          label: "Participation",
          title: "Student Participation Reports",
        },
      ],
    },
    {
      group: "Live",
      items: [
        {
          to: "/real-time",
          label: "Real-Time View",
          title: "Real-Time Cohort View",
        },
      ],
    },
  ],
  it_academic_integrity: [
    {
      group: "Integrity",
      items: [
        {
          to: "/",
          label: "Flagged Cases",
          title: "Academic Integrity & Exam Monitoring",
        },
        {
          to: "/item-analysis",
          label: "Exam Analysis",
          title: "Item Analysis Reports",
        },
        {
          to: "/real-time",
          label: "Live Exam Monitor",
          title: "Live Monitoring · Every University Exam",
        },
      ],
    },
  ],
  student: [
    {
      group: "My learning",
      items: [
        {
          to: "/",
          label: "My Progress",
          title: "My Personal Dashboard",
        },
      ],
    },
  ],
};

export { roleHome };

const emptyAffiliation: UserAffiliation = {
  university: "Benha National University",
  sector: null,
  college: null,
  label: "Benha National University",
};

function affiliationFromUser(
  user: DemoUser,
  extra?: UserAffiliation,
): UserAffiliation {
  return extra ?? emptyAffiliation;
}

function viewerFromUser(
  user: DemoUser,
  label: string,
  level: ViewerScope["level"],
): ViewerScope {
  return {
    userId: user.id,
    role: user.role,
    scopeId: user.scopeId,
    programs: extraPrograms(user),
    courseIds: user.courseIds ?? [],
    courseCodes: user.courses?.map((c) => c.code) ?? [],
    label,
    level,
  };
}

function extraPrograms(user: DemoUser): string[] {
  return [];
}

interface RoleContextValue {
  role: Role;
  user: DemoUser;
  setRole: (role: Role) => void;
  setUser: (userId: string) => void;
  scopeId: string | null;
  displayRole: string;
  affiliation: UserAffiliation;
  viewer: ViewerScope;
}

function userFromToken(token: string | null): DemoUser | null {
  const userId = userIdFromToken(token);
  const role = roleFromToken(token) ?? sessionRoleForToken(token);
  if (!userId || !role) return null;
  const scopeId = scopeIdFromToken(token);
  const studentId = studentIdFromToken(token);
  return {
    id: userId,
    name: userId,
    title: roleLabels[role],
    initials: userId.slice(0, 2).toUpperCase(),
    role,
    scopeId,
    ...(studentId ? { studentId } : {}),
  };
}

function userFromMe(me: MeResponse): DemoUser {
  const role = me.role as Role;
  return {
    id: me.user_id,
    name: me.name || me.user_id,
    title: me.title || roleLabels[role] || me.role,
    initials: me.initials || (me.name || me.user_id).slice(0, 2).toUpperCase(),
    role,
    scopeId: me.scope_id,
    courseIds: me.course_ids ?? [],
    courses: me.courses ?? [],
    ...(me.student_id ? { studentId: me.student_id } : {}),
  };
}

function affiliationFromMe(me: MeResponse): UserAffiliation {
  return {
    university: me.university_name || "Benha National University",
    sector: me.sector_name ?? null,
    college: me.college_name ?? null,
    label: me.scope_label || me.university_name || "Benha National University",
  };
}

function levelFromMe(me: MeResponse): ViewerScope["level"] {
  if (me.role === "it_academic_integrity") return "global";
  if (me.role === "professor") return "course";
  if (
    me.scope_level === "sector" ||
    me.scope_level === "program" ||
    me.scope_level === "university"
  ) {
    return me.scope_level;
  }
  return "university";
}

const fallbackUser: DemoUser = {
  id: "",
  name: "",
  title: "",
  initials: "",
  role: "senior_management",
  scopeId: null,
};

const RoleContext = createContext<RoleContextValue>({
  role: "senior_management",
  user: fallbackUser,
  setRole: () => {},
  setUser: () => {},
  scopeId: null,
  displayRole: "Senior Management",
  affiliation: emptyAffiliation,
  viewer: viewerFromUser(fallbackUser, emptyAffiliation.label, "university"),
});

export function RoleProvider({ children }: { children: ReactNode }) {
  const [tokenUser, setTokenUser] = useState<DemoUser | null>(() =>
    userFromToken(getAuthToken()),
  );
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  useEffect(() => {
    const token = getAuthToken();
    const next = userFromToken(token);
    if (next && (next.id !== tokenUser?.id || next.role !== tokenUser?.role)) {
      setTokenUser(next);
    }
    if (
      typeof window !== "undefined" &&
      !token &&
      window.location.pathname !== "/login"
    ) {
      window.location.href = "/login";
    }
  }, [pathname, tokenUser?.id, tokenUser?.role]);

  const meQuery = useQuery({
    queryKey: ["me", tokenUser?.id],
    queryFn: getMe,
    enabled: Boolean(tokenUser?.id),
    staleTime: 60_000,
  });

  useEffect(() => {
    const me = meQuery.data;
    if (!me?.user_id || !me.role) return;
    rememberSessionRole(me.user_id, me.role);
    if (pathname === "/login") return;
    const slug = pathname.split("/").filter(Boolean)[0];
    if (!slug || !SLUG_ROLE[slug]) return;
    const expected = ROLE_SLUG[me.role as Role];
    if (expected && slug !== expected) {
      window.location.replace(roleHome(me.role as Role));
    }
  }, [meQuery.data, pathname]);

  const user = meQuery.data
    ? userFromMe(meQuery.data)
    : (tokenUser ?? fallbackUser);
  const role = user.role;
  const affiliation = meQuery.data
    ? affiliationFromMe(meQuery.data)
    : emptyAffiliation;
  const displayRole = meQuery.data?.display_role || roleLabels[role];
  const viewer = viewerFromUser(
    user,
    meQuery.data?.scope_label || affiliation.label,
    meQuery.data ? levelFromMe(meQuery.data) : "university",
  );

  const value = useMemo(
    () => ({
      role,
      user,
      setRole: (_next: Role) => {},
      setUser: (_nextId: string) => {},
      scopeId: user.scopeId,
      displayRole,
      affiliation,
      viewer,
    }),
    [role, user, displayRole, affiliation, viewer],
  );

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole() {
  return useContext(RoleContext);
}

export function displayRoleLabel(user: DemoUser): string {
  return user.title || roleLabels[user.role];
}

export function affiliationForScope(_scopeId?: string | null): UserAffiliation {
  return emptyAffiliation;
}
