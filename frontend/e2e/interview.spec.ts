import { expect, test, type Page } from "@playwright/test";

const RECORD_MS = Number(process.env.RECORD_MS ?? 3000);
const QUESTIONS = Number(process.env.E2E_QUESTIONS ?? 3);

async function signUp(page: Page) {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Name").fill("E2E Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Sign up" }).click();
  await expect(page.getByRole("heading", { name: /ready to practise/i })).toBeVisible();
  return email;
}

async function startInterview(page: Page, role = "Data Analyst") {
  await page.getByLabel("Job role").selectOption(role);
  await page.getByLabel("Level").selectOption("Junior");
  await page.getByLabel("Questions").selectOption(String(QUESTIONS));
  await page.getByRole("button", { name: "Start interview" }).click();
  await expect(page).toHaveURL(/\/interview\/[0-9a-f-]{36}$/, { timeout: 90_000 });
  await expect(page.getByTestId("question-text").filter({ visible: true })).toBeVisible();
}

async function recordAnswer(page: Page) {
  await page.getByRole("button", { name: "Start recording" }).click();
  await expect(page.getByRole("button", { name: "Stop recording" })).toBeVisible();
  await page.waitForTimeout(RECORD_MS);
  await page.getByRole("button", { name: "Stop recording" }).click();
  await page.getByRole("button", { name: "Submit answer" }).click();
  await expect(page.getByTestId("answer-feedback").filter({ visible: true })).toBeVisible({ timeout: 180_000 });
}

test("sign up, answer every question by voice, get feedback, see history and progress", async ({ page }) => {
  await signUp(page);
  await startInterview(page);

  for (let i = 0; i < QUESTIONS; i++) {
    await expect(page.getByText(`Question ${i + 1} of ${QUESTIONS}`)).toBeVisible();
    await recordAnswer(page);
    const fb = page.getByTestId("answer-feedback").filter({ visible: true });
    await expect(fb.getByText("Overall")).toBeVisible();
    if (i < QUESTIONS - 1) await page.getByRole("button", { name: "Next question" }).click();
  }

  await page.getByRole("button", { name: "Finish interview" }).click();
  await expect(page).toHaveURL(/\/results$/, { timeout: 90_000 });
  const results = page.getByTestId("results").filter({ visible: true });
  await expect(results.getByTestId("summary")).not.toBeEmpty();
  await expect(results.getByText(`${QUESTIONS} of ${QUESTIONS} answered`)).toBeVisible();

  await page.getByRole("navigation").getByRole("link", { name: "History" }).click();
  const table = page.getByTestId("history-table").filter({ visible: true });
  await expect(table.getByText("Junior Data Analyst")).toBeVisible();
  await expect(table.getByRole("link", { name: "View" })).toBeVisible();

  await page.getByRole("navigation").getByRole("link", { name: "Progress" }).click();
  const progress = page.getByTestId("progress").filter({ visible: true });
  await expect(progress.getByTestId("chart-scores")).toBeVisible();
  await expect(progress.getByTestId("skills-table").getByText("Relevance")).toBeVisible();
  await expect(progress.getByText("1 interview ·")).toBeVisible();
});

test("microphone permission denied shows a clear message", async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () =>
      Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
  });
  await signUp(page);
  await startInterview(page);
  await page.getByRole("button", { name: "Start recording" }).click();
  const err = page.getByTestId("recorder-error").filter({ visible: true });
  await expect(err).toHaveAttribute("data-kind", "denied");
  await expect(err).toContainText("Microphone access was blocked");
});

test("an upload failure keeps the recording and can be retried", async ({ page }) => {
  await signUp(page);
  await startInterview(page);
  await page.route("**/answer", (route) => route.abort("connectionfailed"));
  await page.getByRole("button", { name: "Start recording" }).click();
  await page.waitForTimeout(2500);
  await page.getByRole("button", { name: "Stop recording" }).click();
  await page.getByRole("button", { name: "Submit answer" }).click();
  const err = page.getByTestId("recorder-error").filter({ visible: true });
  await expect(err).toHaveAttribute("data-kind", "upload");
  await expect(err).toContainText("recording is kept");

  await page.unroute("**/answer");
  await page.getByRole("button", { name: "Retry upload" }).click();
  await expect(page.getByTestId("answer-feedback").filter({ visible: true })).toBeVisible({ timeout: 180_000 });
});
