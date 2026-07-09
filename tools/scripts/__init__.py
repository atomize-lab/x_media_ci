"""citeseal tools package.

This package wraps the standalone scripts under ``tools/scripts/`` with a
thin, importable layer so they can be reused from a unified CLI without
modifying the original script behavior.

The original CLI scripts remain runnable as before:

    python tools/scripts/gen_article_md.py --extract ... --out ...

The new entry point adds convenience:

    python tools/citeseal.py md  --tweet-dir <...>
    python tools/citeseal.py pdf --tweet-dir <...>
    python tools/citeseal.py ocr --tweet-dir <...>
    ...
"""
