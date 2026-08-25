type ApiOptions = Omit<RequestInit, "body"> & { body?: unknown };

type ValidationIssue = {
  msg?: unknown;
  type?: unknown;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function apiUrl(path: string): string {
  const desktopBase = typeof window !== "undefined" ? window.mlibDesktop?.apiBase : undefined;
  return `${desktopBase ?? "/api"}${path}`;
}

function validationIssueMessage(issue: ValidationIssue): string {
  const message = typeof issue.msg === "string" ? issue.msg.replace(/^Value error,\s*/i, "") : "";
  if (/[А-Яа-яЁё]/.test(message)) return message;
  if (issue.type === "missing") return "Заполните все обязательные поля";
  if (issue.type === "string_too_short") return "Одно из полей заполнено слишком коротким значением";
  if (issue.type === "string_too_long") return "Одно из полей превышает допустимую длину";
  return "Проверьте корректность заполненных полей";
}

function responseErrorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .filter((issue): issue is ValidationIssue => Boolean(issue) && typeof issue === "object")
        .map(validationIssueMessage);
      const uniqueMessages = [...new Set(messages)];
      if (uniqueMessages.length) return uniqueMessages.join(". ");
    }
  }
  return `Ошибка запроса (${status})`;
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...options,
      body,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(
      "Не удалось связаться с сервером. Проверьте подключение и повторите попытку.",
      0,
    );
  }
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {}
    throw new ApiError(responseErrorMessage(payload, response.status), response.status);
  }
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("Сервер вернул некорректный ответ", response.status);
  }
}

export function artworkUrl(id: string | null | undefined, size: 64 | 256 | 512 = 256): string | null {
  return id ? apiUrl(`/music/artwork/${id}/${size}`) : null;
}

export function streamUrl(trackId: string): string {
  return apiUrl(`/music/tracks/${trackId}/stream`);
}

export function movieStreamUrl(fileId: string): string {
  return apiUrl(`/movie/files/${fileId}/stream`);
}

export function bookCoverUrl(bookId: string): string {
  return apiUrl(`/books/${bookId}/cover`);
}

export function bookContentUrl(bookId: string): string {
  return apiUrl(`/books/${bookId}/content`);
}

export function collectionPhotoUrl(photoId: string, size: "thumb" | "full" = "thumb"): string {
  return apiUrl(`/collections/photos/${photoId}/${size}`);
}
