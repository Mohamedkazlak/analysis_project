import { createFileRoute, redirect } from "@tanstack/react-router";
import { ensureActiveRole, ROLE_SLUG } from "@/lib/auth/role-guards";

export const Route = createFileRoute("/")({
  beforeLoad: async () => {
    if (typeof window === "undefined") {
      throw redirect({ to: "/login" });
    }
    const role = await ensureActiveRole();
    if (!role) {
      throw redirect({ to: "/login" });
    }
    throw redirect({ to: "/$role", params: { role: ROLE_SLUG[role] } });
  },
  component: () => null,
});
