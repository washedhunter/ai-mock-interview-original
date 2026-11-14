import { defineConfig } from "@playwright/test";

import base from "./playwright.config";

// Real-voice run against the real stack (Gemini + Whisper), one step at a time; see e2e-voice/README.md.
export default defineConfig({
  ...base,
  testDir: "./e2e-voice",
  timeout: 300_000,
  retries: 0,
  reporter: [["list"]],
});
