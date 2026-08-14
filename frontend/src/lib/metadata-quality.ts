import type { MetadataIssue } from "@/lib/types";

export const METADATA_ISSUE_LABELS: Record<MetadataIssue, string> = {
  missing_title: "Нет корректного названия",
  unknown_artist: "Неизвестный исполнитель",
  missing_album: "Не указан альбом",
  missing_genre: "Не указан жанр",
  missing_year: "Не указан год",
};

export function metadataIssueText(issues: MetadataIssue[]): string {
  return issues.map((issue) => METADATA_ISSUE_LABELS[issue]).join(" · ");
}
