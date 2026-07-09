# Hermes Agent: Consuming an Agent Bundle

## Prerequisites

Export a bundle first:

```bash
cs export-agent \
  --tweet-dir path/to/tweet_dir \
  --output my_bundle \
  --hash-media
```

## Direct File Consumption

In a Hermes session, simply ask:

```
Read the file my_bundle/bundle.json and summarize the archived post.
Also check the trust_flags to see if there are any data quality issues.
```

Hermes will use its `read_file` tool to load the bundle manifest directly.

## Multi-Bundle Research Workflow

Export multiple bundles, then use Hermes for cross-item analysis:

```bash
mkdir research_bundles
cs export-agent --tweet-dir tweet_1 --output research_bundles/item_1
cs export-agent --tweet-dir tweet_2 --output research_bundles/item_2
cs export-agent --tweet-dir tweet_3 --output research_bundles/item_3
```

In Hermes:

```
Search through all bundle.json files under research_bundles/.
Find items that mention "AI agents" in their text_excerpt.
For each matching item, report:
- The author_handle and captured_at date
- A 1-sentence summary
- Whether trust_flags.media_verified is true
```

## Automated Pipeline Example

Use Hermes skills to build a recurring research digest:

1. **Export**: Run `cs export-agent` on new archived items
2. **Read**: Hermes reads each `bundle.json` via `read_file`
3. **Summarize**: Hermes generates per-item summaries
4. **Cross-reference**: Hermes checks `related_items` for thread connections
5. **Report**: Hermes compiles a research digest with citations

### Example Hermes Session

```
I have 5 agent bundles in the bundles/ directory. For each one:
1. Read bundle.json
2. Extract text_excerpt and author_handle
3. Check if trust_flags.validated is true
4. Note any items with related_items (thread connections)

Then produce a summary table with columns:
| Item ID | Author | Date | Valid | Has Media | Related |
```

## HTTP Consumption (with local server)

If you're running the local server (`cs serve`), Hermes can also fetch
bundles via HTTP using `curl` or Python `requests`:

```
Run: curl -s http://localhost:8000/agent-bundle/example_user/1234567890
Then parse the JSON response and summarize it.
```

## Tips

- **Provenance audit**: Use `provenance.exported_at` and `provenance.source_dir`
  to trace where each bundle came from.
- **Media verification**: Check `trust_flags.media_verified` before trusting
  media paths — if false, some declared media files were missing at export time.
- **OCR quality**: If `trust_flags.has_ocr` is false, the item has no OCR text;
  don't ask the agent to analyze image content.
- **Citation**: Use `citation_label` directly for consistent referencing.
