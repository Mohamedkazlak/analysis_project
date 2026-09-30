import { createFileRoute, useNavigate, redirect } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ROLE_SLUG, ensureActiveRole, roleHome } from "@/lib/auth/role-guards";
import { rememberSessionRole, setAuthToken } from "@/lib/auth/token";
import { BACKEND_URL } from "@/lib/api";
import { useLocale } from "@/lib/i18n";

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
  const { locale, messages, toggleLocale } = useLocale();
  const l = messages.login;
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setError("");
  }, [locale]);

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
        throw new Error(l.invalidCredentials);
      }

      const data = await res.json();
      setAuthToken(data.access_token);

      const meRes = await fetch(`${BACKEND_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (!meRes.ok) {
        throw new Error(l.invalidCredentials);
      }
      const me = await meRes.json();

      const role = me.role as keyof typeof ROLE_SLUG;
      if (!ROLE_SLUG[role]) {
        throw new Error(l.noDashboard);
      }
      rememberSessionRole(me.user_id, role);
      // Full navigation (not the SPA `navigate()`) so RoleProvider remounts
      // and re-reads the freshly-written token. RoleProvider's sync effect
      // only re-checks the token when its own derived role/user state
      // changes, so a client-side transition right after login would keep
      // showing the previous (default) role's nav until a manual reload.
      window.location.href = roleHome(role);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : l.failed);
    } finally {
      setLoading(false);
    }
  };

  const switchLabel =
    locale === "en"
      ? messages.shell.switchToArabic
      : messages.shell.switchToEnglish;

  return (
    <div className="flex min-h-dvh w-full items-center justify-center bg-gray-50 p-4 sm:p-6">
      <div className="relative w-full max-w-sm rounded-xl bg-white p-6 shadow-sm ring-1 ring-gray-900/5 sm:p-8">
        <button
          type="button"
          onClick={toggleLocale}
          className="absolute end-4 top-4 rounded-md px-2.5 py-1 text-[12px] font-semibold text-indigo-700 ring-1 ring-indigo-200 transition hover:bg-indigo-50"
          aria-label={switchLabel}
        >
          {switchLabel}
        </button>

        <div className="mb-6 text-center">
          <img
            src="/brand-logo.png"
            alt={l.logoAlt}
            className="mx-auto mb-4 h-14 w-auto object-contain"
          />
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            {l.title}
          </h1>
          <p className="mt-2 text-sm text-gray-600">{l.subtitle}</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-900">
              {l.userId}
            </label>
            <input
              type="text"
              value={id}
              onChange={(e) => setId(e.target.value)}
              className="mt-2 block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
              placeholder={l.userIdPlaceholder}
              autoComplete="username"
              dir="ltr"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-900">
              {l.password}
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-2 block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
              autoComplete="current-password"
              dir="ltr"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="flex w-full justify-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-60"
          >
            {loading ? l.submitting : l.submit}
          </button>
        </form>
      </div>
    </div>
  );
}
