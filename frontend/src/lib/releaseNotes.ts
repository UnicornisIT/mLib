export type ReleaseNoteIcon = "key" | "eye" | "motion" | "brand" | "shield";

export type ReleaseAnnouncement = {
  version: string;
  title: string;
  intro: string;
  notes: Array<{
    icon: ReleaseNoteIcon;
    title: string;
    description: string;
  }>;
};

const announcements: Record<string, ReleaseAnnouncement> = {
  "0.0.2-alpha": {
    version: "0.0.2-alpha",
    title: "Что нового в mLib",
    intro: "В этой версии мы сделали доступ к библиотеке надёжнее, а ежедневную работу — заметно удобнее.",
    notes: [
      {
        icon: "key",
        title: "Восстановление доступа",
        description: "Забытый пароль теперь можно безопасно сбросить и в приложении, и через сайт.",
      },
      {
        icon: "eye",
        title: "Пароль под контролем",
        description: "Во всех полях пароля можно временно показать введённые символы.",
      },
      {
        icon: "motion",
        title: "Более удобный интерфейс",
        description: "Текст стал крупнее, прокрутка — плавнее, а переходы к разделам — точнее.",
      },
      {
        icon: "brand",
        title: "Обновлённый образ mLib",
        description: "Появились новая системная иконка и favicon, а знакомые логотипы разделов сохранены.",
      },
      {
        icon: "shield",
        title: "Усиленная защита",
        description: "Ключи восстановления одноразовые, а прежние сеансы завершаются после смены пароля.",
      },
    ],
  },
};

export function getReleaseAnnouncement(version: string) {
  return announcements[version] ?? null;
}
