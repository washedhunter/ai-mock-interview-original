"""`interview-api download-model [name]`: fetch a faster-whisper model (used at image build time)."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] != "download-model":
        print("usage: interview-api download-model [MODEL ...]  (default: $WHISPER_MODEL)")
        return 2
    from faster_whisper import download_model

    from .config import get_settings

    s = get_settings()
    for name in args[1:] or [s.whisper_model]:
        path = download_model(name, cache_dir=s.whisper_download_root)
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
