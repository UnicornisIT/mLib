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
  "0.0.5-alpha": {
    version: "0.0.5-alpha",
    title: "Что нового в mLib",
    intro: "В этой версии музыку можно перенести из других сервисов и собрать в каталог в духе Apple Music.",
    notes: [
      {
        icon: "motion",
        title: "Перенос фонотеки",
        description: "Загрузите экспорт Apple Music или TuneMyMusic — треки, альбомы и плейлисты появятся в каталоге.",
      },
      {
        icon: "brand",
        title: "Каталог musicLib",
        description: "Обложки, альбомы, исполнители и жанры каталога; файл можно перетащить прямо на карточку трека.",
      },
      {
        icon: "eye",
        title: "Поиск по мере ввода",
        description: "Поиск в шапке находит исполнителей, треки и альбомы без Enter и не путается в регистре кириллицы.",
      },
      {
        icon: "shield",
        title: "Аккуратнее на любом экране",
        description: "Анимации на главных экранах больше не обрезаются, а кнопки на телефоне не теряют подписи.",
      },
    ],
  },
  "0.0.4-alpha": {
    version: "0.0.4-alpha",
    title: "Что нового в mLib",
    intro: "В этой версии мы исправили загрузку файлов и ускорили запуск после обновления.",
    notes: [
      {
        icon: "motion",
        title: "Загрузка треков и книг",
        description: "Музыка и книги снова загружаются в приложении для Windows.",
      },
      {
        icon: "shield",
        title: "Надёжная докачка видео",
        description: "Прерванная загрузка видео продолжается без повреждения файла.",
      },
      {
        icon: "key",
        title: "Быстрый запуск после обновления",
        description: "Перед обновлением базы сохраняется только она сама, поэтому большие библиотеки запускаются быстро.",
      },
    ],
  },
  "0.0.3-alpha": {
    version: "0.0.3-alpha",
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
