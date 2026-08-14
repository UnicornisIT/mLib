import { expect, test } from "@playwright/test";
import { Buffer } from "node:buffer";
import { deflateSync } from "node:zlib";

const username = "release-user";
const password = "correct horse battery staple";

function taggedWav() {
  const sampleRate = 8_000;
  const seconds = 3;
  const samples = sampleRate * seconds;
  const pcm = Buffer.alloc(samples * 2);
  for (let index = 0; index < samples; index += 1) {
    const sample = Math.round(Math.sin((2 * Math.PI * 440 * index) / sampleRate) * 5_000);
    pcm.writeInt16LE(sample, index * 2);
  }
  const chunk = (id: string, data: Buffer) => {
    const value = Buffer.alloc(8 + data.length + (data.length % 2));
    value.write(id, 0, 4, "ascii");
    value.writeUInt32LE(data.length, 4);
    data.copy(value, 8);
    return value;
  };
  const format = Buffer.alloc(16);
  format.writeUInt16LE(1, 0);
  format.writeUInt16LE(1, 2);
  format.writeUInt32LE(sampleRate, 4);
  format.writeUInt32LE(sampleRate * 2, 8);
  format.writeUInt16LE(2, 12);
  format.writeUInt16LE(16, 14);
  const syncSafe = (value: number) => Buffer.from([(value >> 21) & 0x7f, (value >> 14) & 0x7f, (value >> 7) & 0x7f, value & 0x7f]);
  const frame = (id: string, data: Buffer) => Buffer.concat([Buffer.from(id, "ascii"), syncSafe(data.length), Buffer.alloc(2), data]);
  const textFrame = (id: string, value: string) => frame(id, Buffer.concat([Buffer.from([3]), Buffer.from(value, "utf8")]));
  const crc32 = (input: Buffer) => {
    let value = 0xffffffff;
    for (const byte of input) {
      value ^= byte;
      for (let bit = 0; bit < 8; bit += 1) value = (value >>> 1) ^ (0xedb88320 & -(value & 1));
    }
    return (value ^ 0xffffffff) >>> 0;
  };
  const pngChunk = (name: string, data: Buffer) => {
    const type = Buffer.from(name, "ascii");
    const output = Buffer.alloc(12 + data.length);
    output.writeUInt32BE(data.length, 0);
    type.copy(output, 4);
    data.copy(output, 8);
    output.writeUInt32BE(crc32(Buffer.concat([type, data])), 8 + data.length);
    return output;
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(32, 0); header.writeUInt32BE(32, 4); header[8] = 8; header[9] = 2;
  const rows = Buffer.concat(Array.from({ length: 32 }, () => Buffer.concat([Buffer.from([0]), Buffer.alloc(32 * 3, 120)])));
  const png = Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), pngChunk("IHDR", header), pngChunk("IDAT", deflateSync(rows)), pngChunk("IEND", Buffer.alloc(0))]);
  const frames = Buffer.concat([
    textFrame("TIT2", "Release Track"),
    textFrame("TPE1", "Test Artist"),
    textFrame("TPE2", "Test Artist"),
    textFrame("TALB", "Release Album"),
    textFrame("TCON", "Electronic"),
    textFrame("TRCK", "1/1"),
    frame("APIC", Buffer.concat([Buffer.from([3]), Buffer.from("image/png\0", "ascii"), Buffer.from([3, 0]), png])),
  ]);
  const id3 = Buffer.concat([Buffer.from("ID3\x04\x00\x00", "binary"), syncSafe(frames.length), frames]);
  const body = Buffer.concat([chunk("fmt ", format), chunk("data", pcm), chunk("id3 ", id3)]);
  const wave = Buffer.alloc(12);
  wave.write("RIFF", 0, 4, "ascii");
  wave.writeUInt32LE(body.length + 4, 4);
  wave.write("WAVE", 8, 4, "ascii");
  return Buffer.concat([wave, body]);
}

async function setup(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: /Начать|Войти/ })).toBeVisible({ timeout: 30_000 });
  if (await page.getByRole("button", { name: "Начать" }).isVisible()) {
    await page.getByLabel("Имя пользователя").fill(username);
    await page.getByLabel("Пароль").fill(password);
    await page.getByRole("button", { name: "Начать" }).click();
  } else {
    await page.getByLabel("Имя пользователя").fill(username);
    await page.getByLabel("Пароль").fill(password);
    await page.getByRole("button", { name: "Войти" }).click();
  }
  await expect(page.getByRole("heading", { name: "Что откроем сегодня?" })).toBeVisible({ timeout: 30_000 });
}

test.describe("release smoke", () => {
  test("first run, media workflow and persistence", async ({ page }) => {
    test.skip(test.info().project.name !== "desktop-chromium");
    await setup(page);
    const browserErrors: string[] = [];
    page.on("console", (message) => { if (message.type() === "error") browserErrors.push(message.text()); });
    page.on("pageerror", (error) => browserErrors.push(error.message));

    await page.goto("/music");
    await page.getByRole("button", { name: "Добавить первую музыку", exact: true }).click();
    await page.locator('input[type="file"]').setInputFiles({ name: "release-track.wav", mimeType: "audio/wav", buffer: taggedWav() });
    await page.getByRole("button", { name: /Загрузить 1/ }).click();
    await expect(page.getByText(/Добавлено|Трек добавлен/)).toBeVisible({ timeout: 30_000 });
    await page.getByRole("dialog", { name: "Добавить музыку" }).getByRole("button", { name: "Закрыть" }).last().click();

    await expect(page.getByRole("button", { name: "Release Track" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Test Artist" }).first()).toBeVisible();
    await expect(page.locator('img[alt="Release Track"]').first()).toBeVisible();

    await page.getByRole("button", { name: "Release Track" }).dblclick();
    await expect(page.getByRole("button", { name: "Пауза" })).toBeVisible();
    await page.getByLabel("Позиция воспроизведения").fill("1");
    await page.getByRole("main").getByRole("button", { name: "Избранное" }).click();
    await page.getByRole("contentinfo", { name: "Музыкальный плеер" }).getByRole("button", { name: "Пауза" }).click();

    await page.goto("/music/playlists");
    await page.getByRole("button", { name: "Создать плейлист" }).first().click();
    await page.getByLabel("Название").fill("Release Playlist");
    await page.getByRole("button", { name: "Создать", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Release Playlist" })).toBeVisible();

    await page.goto("/music/tracks");
    await page.getByRole("button", { name: "Действия" }).click();
    await page.locator(".action-menu").getByRole("button", { name: "Добавить в плейлист" }).click();
    await page.getByRole("button", { name: /Release Playlist/ }).click();
    await expect(page.getByText(/добавлен в «Release Playlist»/)).toBeVisible();

    await page.getByRole("button", { name: "Действия" }).click();
    await page.getByRole("button", { name: "Редактировать" }).click();
    await page.getByLabel("Название").fill("Release Track Edited");
    await page.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByRole("main").getByRole("button", { name: "Release Track Edited" })).toBeVisible();

    await page.getByLabel("Поиск по медиатеке").fill("Track Edited");
    await page.getByLabel("Поиск по медиатеке").press("Enter");
    await expect(page.getByRole("main").getByRole("button", { name: "Release Track Edited" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("main").getByRole("button", { name: "Release Track Edited" })).toBeVisible();

    await page.getByRole("button", { name: "Выйти" }).click();
    await expect(page.getByRole("heading", { name: "Войдите в mLib" })).toBeVisible();
    await page.getByLabel("Имя пользователя").fill(username);
    await page.getByLabel("Пароль").fill("wrong password");
    await page.getByRole("button", { name: "Войти" }).click();
    await expect(page.getByText("Неверное имя пользователя или пароль")).toBeVisible();
    await page.getByLabel("Пароль").fill(password);
    await page.getByRole("button", { name: "Войти" }).click();
    await expect(page.getByRole("heading", { name: "Что откроем сегодня?" })).toBeVisible();
    await page.goto("/music/playlists");
    await page.getByRole("button", { name: /Release Playlist/ }).click();
    await expect(page.getByRole("main").getByText("Release Track Edited").first()).toBeVisible();
    const unexpectedErrors = browserErrors.filter((message) => !message.includes("401 (Unauthorized)"));
    expect(unexpectedErrors).toEqual([]);
  });

  test("mobile setup screen has no horizontal overflow", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "mobile-chromium");
    await page.goto("/login");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(overflow).toBe(false);
    await expect(page.getByRole("button", { name: /Войти|Начать/ })).toBeVisible();
  });

  test("release routes fit the supported viewport matrix", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium");
    test.setTimeout(180_000);
    await setup(page);

    const viewports = [
      { width: 1920, height: 1080 },
      { width: 1440, height: 900 },
      { width: 1280, height: 720 },
      { width: 1024, height: 768 },
      { width: 768, height: 1024 },
      { width: 414, height: 896 },
      { width: 390, height: 844 },
      { width: 375, height: 812 },
      { width: 360, height: 800 },
    ];
    const releaseRoutes = ["/", "/music", "/movie", "/books", "/collections", "/games", "/wishes"];

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await page.goto("/");
      await expect(page.getByRole("main")).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
      expect(overflow, `${viewport.width}x${viewport.height} overflows horizontally`).toBe(false);
    }

    for (const viewport of [viewports[0], viewports[4], viewports[8]]) {
      await page.setViewportSize(viewport);
      for (const route of releaseRoutes) {
        await page.goto(route);
        await expect(page.getByRole("main")).toBeVisible();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
        if (overflow) {
          const offenders = await page.evaluate(() => Array.from(document.querySelectorAll<HTMLElement>("body *"))
            .map((element) => ({
              tag: element.tagName.toLowerCase(),
              className: typeof element.className === "string" ? element.className : "",
              left: Math.round(element.getBoundingClientRect().left),
              right: Math.round(element.getBoundingClientRect().right),
              width: Math.round(element.getBoundingClientRect().width),
            }))
            .filter((item) => item.right > document.documentElement.clientWidth + 1 || item.left < -1)
            .sort((a, b) => b.right - a.right)
            .slice(0, 20));
          throw new Error(`${route} overflows at ${viewport.width}x${viewport.height}: ${JSON.stringify(offenders)}`);
        }
      }
    }
  });
});
