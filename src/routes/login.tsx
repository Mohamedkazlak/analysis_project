import { createFileRoute, useNavigate, redirect } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ROLE_SLUG, ensureActiveRole, roleHome } from "@/lib/auth/role-guards";
import { rememberSessionRole, setAuthToken } from "@/lib/auth/token";
import { BACKEND_URL } from "@/lib/api";

const DEMO_ACCOUNT_GROUPS = [
  {
    heading: "Senior management",
    badge: "bg-blue-50 text-blue-700 ring-blue-700/10",
    route: "/senior-management",
    accounts: [
      { id: "u-president", title: "President", name: "Prof. Dr. Tamer Samir" },
      {
        id: "u-vp-aa",
        title: "Vice President for Academic Affairs",
        name: "Prof. Dr. Hussein Mahmoud",
      },
      {
        id: "u-dean-eng",
        title: "Engineering Sector Dean",
        name: "Dr. Hana El-Masry",
      },
      {
        id: "u-dean-health",
        title: "Health Sector Dean",
        name: "Prof. Dr. Nadia El-Sherif",
      },
      {
        id: "u-dean-hum",
        title: "Literature Sector Dean",
        name: "Prof. Dr. Khaled Mansour",
      },
    ],
  },
  {
    heading: "Program directors",
    badge: "bg-indigo-50 text-indigo-700 ring-indigo-700/10",
    route: "/program-director",
    accounts: [
      {
        id: "u-pd-cs",
        title: "Computer Science",
        name: "Prof. Dr. Eman Abdel-elghaffar",
      },
      {
        id: "u-pd-ene",
        title: "Energy Sciences",
        name: "Prof. Dr. Mohamed Mostafa",
      },
      {
        id: "u-pd-eng",
        title: "Engineering",
        name: "Prof. Dr. Mahmoud El-Toukhy",
      },
      { id: "u-pd-med", title: "Medicine", name: "Prof. Dr. Ashraf Ismail" },
      { id: "u-pd-den", title: "Dentistry", name: "Prof. Dr. Heba Mahmoud" },
      {
        id: "u-pd-pt",
        title: "Physical Therapy",
        name: "Prof. Dr. Asmaa Mahmoud",
      },
      { id: "u-pd-vet", title: "Veterinary", name: "Prof. Dr. Ahmed Hassan" },
      {
        id: "u-pd-art",
        title: "Visual Arts & Design",
        name: "Prof. Dr. Ghada Mohamed",
      },
      {
        id: "u-pd-eco",
        title: "Economics and Business Administration",
        name: "Prof. Dr. Doaa Aakl",
      },
    ],
  },
  {
    heading: "Academic affairs",
    badge: "bg-purple-50 text-purple-700 ring-purple-700/10",
    route: "/academic-affairs",
    accounts: [
      { id: "u-aa-cs", title: "Computer Science", name: "Sara Mansour" },
      { id: "u-aa-ene", title: "Energy Sciences", name: "Dina Farouk" },
      { id: "u-aa-eng", title: "Engineering", name: "Omar Khalil" },
      { id: "u-aa-med", title: "Medicine", name: "Rania Hassan" },
      { id: "u-aa-den", title: "Dentistry", name: "Mostafa Adel" },
      { id: "u-aa-pt", title: "Physical Therapy", name: "Nourhan Saleh" },
      { id: "u-aa-vet", title: "Veterinary", name: "Hossam Ali" },
      { id: "u-aa-art", title: "Visual Arts & Design", name: "Laila Magdy" },
      {
        id: "u-aa-eco",
        title: "Economics and Business Administration",
        name: "Yasmine Fathy",
      },
    ],
  },
  {
    heading: "Professors",
    badge: "bg-pink-50 text-pink-700 ring-pink-700/10",
    route: "/professor",
    accounts: [
      {
        id: "u-prof-cs",
        title: "Computer Science",
        name: "Prof. Tomas Oyelaran",
      },
      {
        id: "u-prof-ene",
        title: "Energy Sciences",
        name: "Prof. Yasser Mansour",
      },
      { id: "u-prof-eng", title: "Engineering", name: "Dr. Hana El-Masry" },
      { id: "u-prof-med", title: "Medicine", name: "Dr. Yasmin Adel" },
      { id: "u-prof-den", title: "Dentistry", name: "Prof. Walid Naguib" },
      { id: "u-prof-pt", title: "Physical Therapy", name: "Dr. Amira Saleh" },
      { id: "u-prof-vet", title: "Veterinary", name: "Prof. Nabil Youssef" },
      {
        id: "u-prof-art",
        title: "Visual Arts & Design",
        name: "Prof. Lina Haddad",
      },
      {
        id: "u-prof-eco",
        title: "Economics and Business Administration",
        name: "Dr. Nour El-Sayed",
      },
    ],
  },
  {
    heading: "University offices",
    badge: "bg-red-50 text-red-700 ring-red-700/10",
    route: "/academic-integrity",
    accounts: [
      {
        id: "u-it-integrity",
        title: "Academic Integrity",
        name: "Layla Nasser",
      },
    ],
  },
  {
    heading: "Student",
    badge: "bg-green-50 text-green-700 ring-green-700/10",
    route: "/student",
    accounts: [{ id: "u-student", title: "Student", name: "Student account" }],
  },
] as const;

export const Route = createFileRoute("/login")({
  beforeLoad: async () => {
    if (typeof window === "undefined") return;
    const role = await ensureActiveRole();
    if (role) {
      throw redirect({ to: "/$role", params: { role: ROLE_SLUG[role] } });
    }
  },
  component: Login,
});

function Login() {
  const navigate = useNavigate();
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void ensureActiveRole().then((role) => {
      if (cancelled || !role) return;
      void navigate({ to: "/$role", params: { role: ROLE_SLUG[role] } });
    });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, password }),
      });

      if (!res.ok) {
        throw new Error("Invalid credentials");
      }

      const data = await res.json();
      setAuthToken(data.access_token);

      const meRes = await fetch(`${BACKEND_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (!meRes.ok) {
        throw new Error("Invalid credentials");
      }
      const me = await meRes.json();

      const role = me.role as keyof typeof ROLE_SLUG;
      if (!ROLE_SLUG[role]) {
        throw new Error("This account has no dashboard");
      }
      rememberSessionRole(me.user_id, role);
      // Full navigation (not the SPA `navigate()`) so RoleProvider remounts
      // and re-reads the freshly-written token. RoleProvider's sync effect
      // only re-checks the token when its own derived role/user state
      // changes, so a client-side transition right after login would keep
      // showing the previous (default) role's nav until a manual reload.
      window.location.href = roleHome(role);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-dvh w-full items-center justify-center bg-gray-50 p-4 sm:p-6">
      <div className="flex max-h-[calc(100dvh-2rem)] w-full max-w-4xl overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-gray-900/5 sm:max-h-[calc(100dvh-3rem)]">
        <div className="grid min-h-0 w-full grid-cols-1 overflow-y-auto md:grid-cols-[minmax(16rem,20rem)_1fr] md:overflow-hidden">
          <div className="flex flex-col justify-center p-6 sm:p-8 md:border-r md:border-gray-200">
            <div className="mb-6 text-center">
              <img
                src="/brand-logo.png"
                alt="BNU logo"
                className="mx-auto mb-4 h-14 w-auto object-contain"
              />
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">
                Sign in
              </h1>
              <p className="mt-2 text-sm text-gray-600">
                Sign in with your user ID and password. You are sent to the
                dashboard for that account.
              </p>
            </div>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-900">
                  User ID
                </label>
                <input
                  type="text"
                  value={id}
                  onChange={(e) => setId(e.target.value)}
                  className="mt-2 block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                  placeholder="e.g. u-president"
                  autoComplete="username"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-900">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-2 block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                  autoComplete="current-password"
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="flex w-full justify-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-60"
              >
                {loading ? "Signing in..." : "Sign in"}
              </button>
            </form>
          </div>

          <div className="flex min-h-0 flex-col border-t border-gray-200 p-5 sm:p-6 md:border-t-0 md:overflow-y-auto">
            <h3 className="mb-3 text-sm font-medium text-gray-900">
              Demo Accounts
            </h3>
            <p className="mb-3 text-xs text-gray-500">
              Each account opens its own dashboard. Use that account&apos;s
              password.
            </p>
            <div className="space-y-4 text-xs text-gray-600">
              {DEMO_ACCOUNT_GROUPS.map((group) => (
                <div key={group.heading}>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="font-semibold text-gray-900">
                      {group.heading}
                    </p>
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset ${group.badge}`}
                    >
                      {group.route}
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {group.accounts.map((account) => (
                      <button
                        key={account.id}
                        type="button"
                        onClick={() => setId(account.id)}
                        className="flex w-full items-start justify-between gap-3 rounded-md px-1 py-0.5 text-left hover:bg-gray-50"
                      >
                        <div className="min-w-0">
                          <span className="font-semibold text-gray-900">
                            {account.id}
                          </span>
                          <p>{account.name}</p>
                        </div>
                        <p className="shrink-0 text-right text-gray-500">
                          {account.title}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
