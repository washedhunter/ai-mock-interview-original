import { defineConfig, devices } from "@playwright/test";

// Runs against an already running stack (docker compose ... up --wait); see the README.
// FAKE_AUDIO=path/to/speech.wav makes Chromium's fake microphone play that file (used to drive a
// real-speech run against real Whisper + Gemini); otherwise it plays a test tone.
const fakeAudio = process.env.FAKE_AUDIO;

export default defineConfig({
  testDir: "./e2e",
  timeout: Number(process.env.E2E_TIMEOUT ?? 120_000),
  expect: { timeout: Number(process.env.E2E_EXPECT_TIMEOUT ?? 30_000) },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    permissions: ["microphone"],
    launchOptions: {
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        ...(fakeAudio ? [`--use-file-for-fake-audio-capture=${fakeAudio}`] : []),
      ],
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
