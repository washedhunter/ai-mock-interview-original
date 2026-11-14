# Real-voice run

Drives the real stack (Gemini + Whisper, no mocks) with spoken audio instead of a test tone.
Chromium's `--use-file-for-fake-audio-capture` plays a WAV file as the microphone, so each answer
is recorded through the real MediaRecorder → upload → Whisper → Gemini path.

Chromium can only play one file per browser launch, so the run is split into steps that share a
logged-in session (`.voice-state.json`, gitignored):

```
VOICE_STEP=setup  npx playwright test -c playwright.voice.config.ts            # sign up, start interview, print questions
FAKE_AUDIO=answer1.wav VOICE_STEP=answer QUESTION=1 RECORD_MS=40000 npx playwright test -c playwright.voice.config.ts
...                                                                             # one per question
VOICE_STEP=finish npx playwright test -c playwright.voice.config.ts             # finish, screenshot results/history/progress
```

The WAV files are speech generated with a text-to-speech engine (Windows `System.Speech`) from
answers written for the questions Gemini asked. Use your own voice with a real browser to try it for real.
