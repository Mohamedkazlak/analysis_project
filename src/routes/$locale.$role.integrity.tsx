import { createFileRoute } from "@tanstack/react-router";
import { IntegrityPage } from "@/components/pages/integrity-page";
import { roleGuard } from "@/lib/auth/role-guards";

export const Route = createFileRoute("/$locale/$role/integrity")({
  beforeLoad: roleGuard("/integrity"),
  head: () => ({
    meta: [
      { title: "Academic Integrity & Exam Monitoring — BNU" },
      {
        name: "description",
        content:
          "Attempt-level monitoring with timings, IP addresses, devices and flagged suspicious patterns.",
      },
      {
        property: "og:title",
        content: "Academic Integrity & Exam Monitoring — BNU",
      },
      {
        property: "og:description",
        content:
          "Attempt-level monitoring with timings, IP addresses, devices and flagged suspicious patterns.",
      },
    ],
  }),
  component: IntegrityPage,
});
