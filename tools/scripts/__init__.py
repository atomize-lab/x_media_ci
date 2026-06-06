"""x_media_ci tools package.

This package wraps the standalone scripts under ``tools/scripts/`` with a
thin, importable layer so they can be reused from a unified CLI without
modifying the original script behavior.

The original CLI scripts remain runnable as before:

    python tools/scripts/gen_article_md.py --extract ... --out ...

The new entry point adds convenience:

    python tools/x_media_ci.py md  --tweet-dir <...>
    python tools/x_media_ci.py pdf --tweet-dir <...>
    python tools/x_media_ci.py ocr --tweet-dir <...>
    ...
"""
