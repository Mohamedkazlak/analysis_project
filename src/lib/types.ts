export type Role =
  | "senior_management"
  | "program_director"
  | "academic_affairs"
  | "professor"
  | "it_academic_integrity"
  | "student";

export type ScopeLevel = "university" | "sector" | "program";

export type ExamStatus = "scheduled" | "in_progress" | "closing" | "closed";
export type AttemptStatus = "absent" | "in_progress" | "submitted" | "void";

export interface OrgScope {
  id: string;
  level: ScopeLevel;
  parentId: string | null;
  code: string;
  name: string; // e.g. "Benha National University", "Engineering & Basic and Applied Sciences", "Computer Science"
  titleForRole: string; // e.g. "President", "VP for Academic Affairs", "Dean", "Program Director"
}

export interface DemoUser {
  id: string;
  name: string;
  title: string;
  initials: string;
  role: Role;
  /** Org tree node. `null` = university-wide / no filter (IT). */
  scopeId: string | null;
  courseIds?: string[];
  studentId?: string;
  courses?: {
    id: string;
    code: string;
    name: string;
    enrolled: number;
    sections: string[];
  }[];
}

export interface UserAffiliation {
  university: string;
  sector: string | null;
  college: string | null;
  label: string;
}

export interface ViewerScope {
  userId: string;
  role: Role;
  scopeId: string | null;
  programs: string[];
  courseIds: string[];
  courseCodes: string[];
  label: string;
  level: "university" | "sector" | "program" | "course" | "global";
}

export type UniversityOffice = "president" | "vp_aa";

export interface Course {
  id: string;
  code: string;
  name: string;
  instructorId: string;
  instructor: string;
  sections: string[];
  enrolled: number;
  credits: number;
  yearLevel: number;
  programId: string;
  sectorId: string;
  program: string;
  sector: string;
}

export interface Exam {
  id: string;
  courseId: string;
  offeringId: string;
  courseCode: string;
  title: string;
  date: string;
  questionCount: number;
  passMark: number;
  status: ExamStatus;
}

export interface Student {
  id: string;
  personId: string;
  studentNumber: string;
  name: string;
  programId: string;
  sectorId: string;
  program: string;
  sector: string;
  section: string;
  cohortYear: number;
}

export interface Enrollment {
  id: string;
  studentId: string;
  courseId: string;
  offeringId: string;
  sectionId: string;
  section: string;
  academicYearId: string;
}

export interface Attempt {
  id: string;
  examId: string;
  studentId: string;
  enrollmentId: string;
  score: number;
  timeTakenMin: number;
  startedAt: string;
  endedAt: string;
  ip: string;
  device: string;
  attemptCount: number;
  participated: boolean;
  lateStart: boolean;
  status: AttemptStatus;
  program: string;
  sector: string;
}

export interface Kpi {
  label: string;
  value: string;
  /** Omitted when there is no real prior-period value to compare against. */
  delta?: string;
  direction?: "up" | "down";
}

export interface ManagementOverview {
  kpis: Kpi[];
  passRateByCourse: {
    course: string;
    passRate: number;
    participants: number;
  }[];
  passRateByCollege: {
    college: string;
    passRate: number;
    participants: number;
    students?: number;
    courses: number;
    attendance: number;
    participation: number;
    expected: number;
    onTime: number;
    late: number;
    absent: number;
    passed: number;
    failed: number;
  }[];
  activityTrend: {
    month: string;
    exams: number;
    participants: number;
    year?: number;
    monthNum?: number;
    termId?: string;
    termName?: string;
  }[];
  examSummaries?: {
    examId: string;
    title: string;
    course: string;
    college: string;
    termId?: string;
    termName?: string;
    month?: string;
    year?: number;
    monthNum?: number;
    sittings: number;
    passed: number;
    failed: number;
    absent: number;
    late: number;
    avgScore: number;
  }[];
  insight: string;
  totals?: {
    exams: number;
    students: number;
    passRate: number;
    attendance: number;
    colleges: number;
  };
  containsSynthetic?: boolean;
}

export interface RankedStudent {
  rank: number;
  studentId: string;
  name: string;
  course: string;
  college: string;
  collegeId: string;
  average: number;
  best: number;
  trend: number;
  status: "Pass" | "Fail";
}

export interface StudentPerformanceReport {
  averageByExam: {
    exam: string;
    average: number;
    course: string;
    college: string;
    collegeId: string;
  }[];
  highest: { name: string; score: number; exam: string };
  lowest: { name: string; score: number; exam: string };
  passFail: { name: string; value: number }[];
  distribution: { bucket: string; students: number }[];
  ranked: RankedStudent[];
  semesterComparison: {
    exam: string;
    course: string;
    college: string;
    collegeId: string;
    current: number | null;
    previous: number | null;
  }[];
  currentTerm: string | null;
  previousTerm: string | null;
  insight: string;
}

export interface QuestionItem {
  id: string;
  examId: string;
  number: number;
  exam: string;
  topic: string;
  prompt: string;
  pctCorrect: number;
  pctIncorrect: number;
  difficultyIndex: number;
  discriminationIndex: number;
  flagged: boolean;
}

export interface ItemAnalysisReport {
  questions: QuestionItem[];
  needsReview: QuestionItem[];
  insight: string;
}

export interface IntegrityRow {
  id: string;
  student: string;
  exam: string;
  startedAt: string;
  endedAt: string;
  ip: string;
  device: string;
  attempts: number;
  flags: string[];
}

export interface IntegritySummaryRow {
  exam: string;
  program: string;
  flagged: number;
  total: number;
}

export interface IntegrityReport {
  rows: IntegrityRow[];
  summary: IntegritySummaryRow[];
  flaggedCount: number;
  totalAttempts: number;
  insight: string;
}

export interface ParticipationReport {
  grain?: "college" | "curriculum" | "exam";
  attemptsPerExam: { exam: string; attempts: number; expected: number }[];
  completionRate: number;
  attendanceRate: number;
  attendanceByCurriculum: {
    course: string;
    attendance: number;
    absentees: number;
    students?: number;
    participated?: number;
  }[];
  avgTimePerExam: { exam: string; minutes: number }[];
  absentees: {
    student: string;
    exam: string;
    reason: "No attempt" | "Late start";
    minutesLate: number;
    college?: string;
  }[];
  insight: string;
}

export interface CoursePerformanceReport {
  averageByCourse: {
    course: string;
    courseCode?: string;
    average: number;
    quality: number;
  }[];
  sections: {
    section: string;
    course: string;
    courseCode?: string;
    college?: string;
    average: number;
    passRate: number;
    enrolled?: number;
  }[];
  assignedCourses?: {
    id: string;
    code: string;
    name: string;
    enrolled: number;
    sections: string[];
  }[];
  insight: string;
}

export interface StrugglingStudent {
  studentId: string;
  name: string;
  college: string;
  course: string;
  lastScore: number;
  average: number;
  trend: number;
  lastActivity: string;
}

export interface LiveExamSitting {
  examId: string;
  exam: string;
  program: string;
  sector: string;
  activeNow: number;
  submitted: number;
  expected: number;
  flagged: number;
  status: "In progress" | "Closing";
}

export interface RealTimeReport {
  students: StrugglingStudent[];
  liveExams: LiveExamSitting[];
  updatedAt: string;
  activeNow: number;
  insight: string;
}

export interface StudentDashboardReport {
  studentName: string;
  college: string;
  sector: string;
  termName: string;
  scoreTimeline: {
    exam: string;
    course: string;
    courseCode: string;
    chartLabel: string;
    date: string;
    score: number;
    classAverage: number;
  }[];
  topics: { topic: string; score: number }[];
  topicsFrom: "questions" | "courses";
  average: number;
  gpa: number | null;
  classAverage: number;
  bestTopic: string;
  weakestTopic: string;
  bestTopicScore: number | null;
  weakestTopicScore: number | null;
  insight: string;
}

export interface StudentDirectoryRow {
  studentId: string;
  name: string;
  program: string;
  section: string;
  overallAverage: number;
  latestYearAverage: number;
  trend: number;
  standing: string;
  status: "Pass" | "Fail";
}

export interface StudentProfileReport {
  studentId: string;
  name: string;
  program: string;
  section: string;
  cohortRank: number;
  cohortSize: number;
  overallAverage: number;
  gpa: number;
  classAverage: number;
  attendance: number;
  totalCredits: number;
  standing: string;
  years: {
    year: string;
    yearLabel: string;
    average: number;
    gpa: number;
    classAverage: number;
    examsTaken: number;
    passRate: number;
    attendance: number;
    credits: number;
    standing: string;
    courses: {
      course: string;
      average: number;
      grade: string;
      credits: number;
    }[];
  }[];
  yearTrend: { year: string; student: number; cohort: number }[];
  courseMatrix: { course: string; values: (number | null)[] }[];
  recentAttempts: {
    exam: string;
    course: string;
    date: string;
    score: number;
    minutes: number;
    status: "Pass" | "Fail" | "No attempt";
  }[];
  topics: { topic: string; score: number }[];
  insight: string;
}
