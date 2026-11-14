import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

const STATE = path.join(__dirname, "..", ".voice-state.json");
const RUN = path.join(__dirname, "..", ".voice-run.json");
const SHOTS = process.env.SHOTS_DIR ?? path.join(__dirname, "..", "..", "docs", "img");
const step = process.env.VOICE_STEP;

test.use({ viewport: { width: 1280, height: 900 } });

test("voice run step", async ({ browser }) => {
  test.skip(!step, "set VOICE_STEP");
  const context = await browser.newContext({
    permissions: ["microphone"],
    storageState: step === "setup" && !process.env.REUSE ? undefined : STATE,
  });
  const page = await context.newPage();

  if (step === "setup") {
    // REUSE=1: start another interview as the same user (keeps the saved session).
    const email = process.env.REUSE
      ? JSON.parse(fs.readFileSync(RUN, "utf8")).email
      : (process.env.VOICE_EMAIL ?? `voice-${Date.now()}@example.com`);
    if (process.env.REUSE) {
      await page.goto("/dashboard");
    } else {
      await page.goto("/signup");
      await page.getByLabel("Name").fill(process.env.VOICE_NAME ?? "Voice Tester");
      await page.getByLabel("Email").fill(email);
      await page.getByLabel("Password").fill("voice-password-123");
      await page.getByRole("button", { name: "Sign up" }).click();
    }
    await expect(page.getByRole("heading", { name: /ready to practise/i })).toBeVisible();
    await page.getByLabel("Job role").selectOption(process.env.VOICE_ROLE ?? "Data Analyst");
    await page.getByLabel("Level").selectOption(process.env.VOICE_LEVEL ?? "Junior");
    await page.getByLabel("Questions").selectOption(process.env.VOICE_QUESTIONS ?? "3");
    await page.getByRole("button", { name: "Start interview" }).click();
    await expect(page).toHaveURL(/\/interview\/[0-9a-f-]{36}$/, { timeout: 120_000 });
    const id = page.url().split("/").pop()!;
    const iv = await (await page.request.get(`/api/interviews/${id}`)).json();
    fs.writeFileSync(RUN, JSON.stringify({ email, id, questions: iv.questions.map((q: { text: string; kind: string; skill: string }) => ({ text: q.text, kind: q.kind, skill: q.skill })) }, null, 2));
    await context.storageState({ path: STATE });
    console.log(fs.readFileSync(RUN, "utf8"));
  }

  if (step === "answer") {
    const run = JSON.parse(fs.readFileSync(RUN, "utf8"));
    const n = Number(process.env.QUESTION);
    await page.goto(`/interview/${run.id}`);
    await page.getByRole("button", { name: new RegExp(`^Question ${n}( \(answered\))?$`) }).click();
    await expect(page.getByText(`Question ${n} of`)).toBeVisible();
    await page.getByRole("button", { name: "Start recording" }).click();
    await page.waitForTimeout(Number(process.env.RECORD_MS ?? 30000));
    await page.getByRole("button", { name: "Stop recording" }).click();
    const t0 = Date.now();
    await page.getByRole("button", { name: "Submit answer" }).click();
    const fb = page.getByTestId("answer-feedback").filter({ visible: true });
    await expect(fb).toBeVisible({ timeout: 240_000 });
    console.log(`answer ${n}: feedback after ${((Date.now() - t0) / 1000).toFixed(1)} s`);
    if (process.env.SHOT) {
      await fb.getByText("Your transcript").click();
      await page.screenshot({ path: path.join(SHOTS, process.env.SHOT), fullPage: true });
    }
  }

  if (step === "finish") {
    const run = JSON.parse(fs.readFileSync(RUN, "utf8"));
    await page.goto(`/interview/${run.id}`);
    page.on("dialog", (d) => d.accept());
    await page.getByRole("button", { name: "Finish interview" }).click();
    await expect(page).toHaveURL(/\/results$/, { timeout: 120_000 });
    await expect(page.getByTestId("summary").filter({ visible: true })).not.toBeEmpty();
    await page.screenshot({ path: path.join(SHOTS, "results.png"), fullPage: true });
    await page.goto("/history");
    await expect(page.getByTestId("history-table").filter({ visible: true })).toBeVisible();
    await page.screenshot({ path: path.join(SHOTS, "history.png"), fullPage: true });
    await page.goto("/progress");
    await expect(page.getByTestId("chart-scores").filter({ visible: true })).toBeVisible();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SHOTS, "progress.png"), fullPage: true });
  }
  await context.close();
});
