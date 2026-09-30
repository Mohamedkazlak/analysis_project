export type { Locale, Messages } from "./types";
export {
  LocaleProvider,
  useLocale,
  speechLanguageForLocale,
} from "./locale-context";
export {
  translateOrgName,
  translatePersonTitle,
  translateScopeLabel,
  translateTermName,
  translateTopicName,
} from "./org-names";

export function translateStanding(
  value: string | null | undefined,
  standing: Record<string, string>,
): string {
  if (!value) return "";
  return standing[value] ?? value;
}
