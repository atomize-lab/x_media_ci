---
name: Good first issue
about: A small, self-contained task suitable for new contributors
title: "[good first issue] "
labels: ["good first issue", "help wanted"]
---

## Summary

A one-sentence description of the task.

## Context

Why does this task exist? Link to any related issues, docs, or roadmap items.

## What needs to be done

A concrete checklist of steps. Be specific about files, functions, or tests involved.

- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

## Skills helpful

- Python (tools layer)
- JSON Schema (if schema-related)
- pytest (if test-related)

No prior experience with the project is required -- the task is designed to be self-contained.

## How to verify

```bash
# Run the relevant tests
python -m pytest tests/test_<relevant>.py -v

# Lint
cd tools && python citeseal.py lint && cd ..
```

## Checklist

- [ ] This task does not involve bulk-scraping or bypassing platform access controls.
- [ ] I have checked existing issues for duplicates.
