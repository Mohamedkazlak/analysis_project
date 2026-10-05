import type { Role } from "../types";

/**
 * Feature toggles for the AI layer.
 *
 * Current-standing rows are ON for staff roles. They are not forecasts.
 * Students only get recommendations.
 */
export const aiConfig: {
  showPredictions: Record<Role, boolean>;
  showInsights: Record<Role, boolean>;
  showWarnings: Record<Role, boolean>;
} = {
  showPredictions: {
    senior_management: true,
    program_director: true,
    academic_affairs: true,
    professor: true,
    it_academic_integrity: true,
    student: false,
  },
  showInsights: {
    senior_management: true,
    program_director: true,
    academic_affairs: true,
    professor: true,
    it_academic_integrity: true,
    student: false,
  },
  showWarnings: {
    senior_management: true,
    program_director: true,
    academic_affairs: true,
    professor: true,
    it_academic_integrity: true,
    student: false,
  },
};

/** Dashboard surfaces that request page-local AI analysis. */
export type AiPage =
  | "overview"
  | "courses"
  | "exam-activity"
  | "performance"
  | "participation"
  | "item-analysis"
  | "integrity"
  | "real-time"
  | "students"
  | "student"
  | "my-progress";

export const AI_PAGE_LABELS: Record<AiPage, string> = {
  overview: "Overview analysis",
  courses: "Course performance analysis",
  "exam-activity": "Exam activity analysis",
  performance: "Student performance analysis",
  participation: "Participation analysis",
  "item-analysis": "Item analysis",
  integrity: "Integrity analysis",
  "real-time": "Live monitoring analysis",
  students: "Student directory analysis",
  student: "Student analysis",
  "my-progress": "My progress analysis",
};
