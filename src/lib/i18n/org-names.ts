/** Presentation-only Arabic labels for demo org units. */

const ORG_AR: Record<string, string> = {
  "Benha National University": "جامعة بنها الأهلية",
  "Engineering and Basic & Applied Sciences":
    "الهندسة والعلوم الأساسية والتطبيقية",
  "Health Sciences": "العلوم الصحية",
  "Literature, Arts and Humanities": "الآداب والفنون والعلوم الإنسانية",
  Engineering: "الهندسة",
  "Energy Sciences": "علوم الطاقة",
  "Computer Science": "علوم الحاسب",
  Medicine: "الطب",
  Dentistry: "طب الأسنان",
  "Physical Therapy": "العلاج الطبيعي",
  Veterinary: "الطب البيطري",
  "Visual Arts and Design": "الفنون البصرية والتصميم",
  "Economics and Business Administration": "الاقتصاد وإدارة الأعمال",
  University: "الجامعة",
};

const TERM_SEASON_AR: Record<string, string> = {
  Fall: "خريف",
  Autumn: "خريف",
  Spring: "ربيع",
  Summer: "صيف",
  Winter: "شتاء",
};

/** Demo course / question-topic labels (EN ↔ AR). */
const TOPIC_AR: Record<string, string> = {
  Physics: "الفيزياء",
  Mathematics: "الرياضيات",
  Programming: "البرمجة",
  Databases: "قواعد البيانات",
  "Database Systems": "قواعد البيانات",
  "Artificial Intelligence": "الذكاء الاصطناعي",
  "Software Engineering": "هندسة البرمجيات",
  "Computer Science": "علوم الحاسب",
  "Information Security": "أمن المعلومات",
  Cybersecurity: "الأمن السيبراني",
  "Web Development": "تطوير الويب",
  Networks: "الشبكات",
  Algorithms: "الخوارزميات",
  "Data Structures": "هياكل البيانات",
  "Operating Systems": "نظم التشغيل",
  "Course assessment": "تقييم المقرر",
  Architecture: "الهندسة المعمارية",
  "Use Cases": "حالات الاستخدام",
  "Sequence Diagrams": "مخططات التسلسل",
  Requirements: "المتطلبات",
  "Data Modeling": "نمذجة البيانات",
  "UI Flows": "تدفقات الواجهة",
  General: "عام",
  None: "لا يوجد",
};

const TOPIC_EN: Record<string, string> = Object.fromEntries(
  Object.entries(TOPIC_AR).map(([en, ar]) => [ar, en]),
);

export function translateOrgName(
  name: string | null | undefined,
  locale: "en" | "ar",
): string {
  if (!name) return "";
  if (locale !== "ar") return name;
  return ORG_AR[name] ?? name;
}

/** Localize a course or question-topic label for display. */
export function translateTopicName(
  name: string | null | undefined,
  locale: "en" | "ar",
): string {
  if (!name) return "";
  if (locale === "ar") return TOPIC_AR[name] ?? name;
  return TOPIC_EN[name] ?? name;
}

/** Translate term labels like "Fall 2025" / "Spring 2026". */
export function translateTermName(
  name: string | null | undefined,
  locale: "en" | "ar",
): string {
  if (!name) return "";
  if (locale !== "ar") return name;
  const match = name.match(/^([A-Za-z]+)\s+(\d{4})$/);
  if (match) {
    const season = TERM_SEASON_AR[match[1]!] ?? match[1]!;
    return `${season} ${match[2]}`;
  }
  let next = name;
  for (const [en, ar] of Object.entries(TERM_SEASON_AR)) {
    next = next.replace(new RegExp(`\\b${en}\\b`, "g"), ar);
  }
  return next;
}

/** Translate affiliation / scope strings that embed English org labels. */
export function translateScopeLabel(
  label: string,
  locale: "en" | "ar",
  copy: {
    universityWide: string;
    sector: string;
    college: string;
  },
): string {
  if (locale !== "ar") return label;
  let next = label;
  for (const [en, ar] of Object.entries(ORG_AR)) {
    next = next.split(en).join(ar);
  }
  return next
    .replace(/\buniversity-wide\b/gi, copy.universityWide)
    .replace(/\bsector\b/gi, copy.sector)
    .replace(/\bcollege\b/gi, copy.college);
}

export function translatePersonTitle(
  name: string,
  locale: "en" | "ar",
): string {
  if (locale !== "ar") return name;
  return name
    .replace(/^Prof\.\s*Dr\.\s*/i, "أ.د. ")
    .replace(/^Dr\.\s*/i, "د. ")
    .replace(/^Prof\.\s*/i, "أ. ");
}
