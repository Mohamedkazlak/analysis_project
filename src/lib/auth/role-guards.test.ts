import { describe, expect, it } from "vitest";
import {
  legacyRedirectTo,
  reportPath,
  roleHome,
  roleHref,
  roleNavigateTarget,
  roleRouteTo,
  roleSlug,
  rolesAllowedForPath,
} from "./role-guards";

describe("role urls", () => {
  it("puts locale and role slug in the home path", () => {
    expect(roleSlug("senior_management")).toBe("senior-management");
    expect(roleHome("senior_management", "en")).toBe("/en/senior-management");
    expect(roleHome("senior_management", "ar")).toBe("/ar/senior-management");
    expect(roleHref("senior_management", "/courses", "en")).toBe(
      "/en/senior-management/courses",
    );
    expect(roleHref("professor", "/management", "ar")).toBe("/ar/professor");
    expect(roleRouteTo("/courses")).toBe("/$locale/$role/courses");
    expect(roleRouteTo("/")).toBe("/$locale/$role");
    expect(roleRouteTo("/my-progress")).toBe("/$locale/$role");
  });

  it("strips locale and role slug when checking report access", () => {
    expect(reportPath("/en/senior-management/courses")).toBe("/courses");
    expect(reportPath("/ar/senior-management")).toBe("/");
    expect(reportPath("/senior-management/courses")).toBe("/courses");
    expect(rolesAllowedForPath("/en/senior-management/courses")).toContain(
      "senior_management",
    );
    expect(rolesAllowedForPath("/en/student/courses")).not.toContain("student");
  });

  it("rewrites leftover unprefixed report urls with locale", () => {
    expect(legacyRedirectTo("/courses", "senior_management", "en")).toBe(
      "/en/senior-management/courses",
    );
    expect(legacyRedirectTo("/management", "senior_management", "ar")).toBe(
      "/ar/senior-management",
    );
    expect(legacyRedirectTo("/students/s7", "professor", "en")).toBe(
      "/en/professor/students/s7",
    );
    expect(
      legacyRedirectTo("/senior-management/courses", "senior_management", "en"),
    ).toBe("/en/senior-management/courses");
    expect(
      legacyRedirectTo(
        "/en/senior-management/courses",
        "senior_management",
        "en",
      ),
    ).toBeNull();
    expect(roleNavigateTarget("/senior-management/courses", "en")).toEqual({
      to: "/$locale/$role/courses",
      params: { locale: "en", role: "senior-management" },
    });
    expect(roleNavigateTarget("/ar/senior-management/courses")).toEqual({
      to: "/$locale/$role/courses",
      params: { locale: "ar", role: "senior-management" },
    });
  });
});
