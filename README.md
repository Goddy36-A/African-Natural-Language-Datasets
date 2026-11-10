# African Natural Language Datasets

Parallel corpora for African-language NLP. The owner's existing Runyankole corpus,
`bible_parallel_corpus_full_v2.json`, is preserved unchanged.

## Uganda regional expansion

These are pragmatic language choices, not claims that a single language represents
all communities in a region.

| Region | Language | ISO 639-3 | Status |
| --- | --- | --- | --- |
| Western | Runyankole | `nyn` | Existing owner corpus; not reprocessed or relicensed |
| Central | Luganda | `lug` | Verified source; builder and automatic generation workflow added |
| Eastern | Ateso | `teo` | Pending a verified verse-indexed source and redistribution license |
| Northern | Acholi | `ach` | Pending a verified verse-indexed source and redistribution license |

**Scope:** this change implements English–Luganda, not four finished regional
corpora. Ateso and Acholi are not fabricated, machine-translated, or silently
replaced by related languages. Their texts were not found in the upstream
collections inspected. A reader website being public does not establish permission
to redistribute a cleaned dataset.

The existing 8.2 MB JSON could not be inspected through the available file-content
tool (it returned empty content), so the new format does **not** claim compatibility
with its schema. No changes are made to that file.

## Sources and licensing

The builder downloads the [BibleNLP eBible extracts](https://github.com/BibleNLP/ebible)
instead of scraping fragile HTML reader pages. Upstream documents that these are
verse-only extracts with headings and footnotes removed, aligned against
`metadata/vref.txt` in original versification.

- Luganda: <https://ebible.org/lug/>, copyright © 2017 Biblica, Inc.;
  **[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)**.
  The original work by Biblica, Inc. is available for free at www.biblica.com and open.bible.
- English: <https://ebible.org/eng-web/>, public-domain source text.
- New Luganda-derived text and corpus contributions are distributed under CC BY-SA
  4.0, **not** a blanket license covering the existing Runyankole file.
- Each build includes original source copyright notices and an attribution/change
  notice. The original Luganda notice contains an inconsistent Akuapem Twi
  paragraph; it is preserved rather than silently corrected.
- Dataset naming does not use the sources' trademarks as a derivative edition name.

Reviewed copyright notices are pinned by Git blob hashes. If either notice changes,
the build stops for manual review before downloading scripture texts. All source
files are fetched at one resolved upstream commit, with SHA-256 checksums recorded.

## Generate the actual corpus

Python **3.11+**, no third-party packages. From the repository root, the same commands
work in Bash and PowerShell (use `py -3.11` instead of `python` if appropriate):

```bash
python -m unittest discover -s tests -v
python scripts/build_uganda_corpus.py
```

To reproduce a published build, use `source_revision` from its manifest, along with
the same builder/config versions (their checksums are also in the manifest):

```bash
python scripts/build_uganda_corpus.py --revision FULL_40_CHARACTER_UPSTREAM_COMMIT_SHA
```

The **Uganda Bible corpus** workflow runs tests and attempts the download/build on
pushes to `forge/uganda-bible-corpora`. On success it uploads an artifact and commits
`data/uganda/eng-lug/` back to **that feature branch only**. It never commits to main.
Repository Actions must be enabled and permit the job's `contents: write` permission.
PR events run synthetic unit tests only, without write permissions.

A builder commit alone is **not** proof of a generated dataset. Check the workflow,
the generated-data commit and `quality-report.json` for actual completion/counts.
If automatic execution is unavailable, run the commands above on the feature branch
and commit the resulting directory. No downloaded corpus or test-pass claim is
implied by this README.

### Generated files

| File | Contents |
| --- | --- |
| `parallel.jsonl` | One object per retained pair: `verse_id`, `translation.eng`, `translation.lug`, `quality_flags` |
| `parallel.tsv` | UTF-8 columns `verse_id`, `eng`, `lug` |
| `quality-report.json` | Exact retained/rejected counts, cleaning counts, book coverage |
| `rejected.jsonl` | Removed verse references and reasons, without rejected text |
| `build-manifest.json` | Immutable upstream revision, source/artifact hashes and build provenance |
| `ATTRIBUTION.md`, `*-source-notice.html` | Source terms, attribution and transformation notice |

## Cleaning and alignment policy

1. Preserve **every blank line until alignment**. Require equal source/reference line
   counts, unique well-formed verse IDs and valid UTF-8; fail rather than truncate.
2. Align each language using the same canonical verse references, never by sentence
   order or independently filtered line positions.
3. Exclude **entire merged-verse ranges**, including the initial verse containing the
   combined text. Upstream represents subsequent verses with `<range>` markers.
4. Apply NFC Unicode normalization, collapse whitespace and remove BOM, zero-width
   spaces and soft hyphens. Preserve accents, apostrophes, punctuation, case and digits.
5. Reject empty, corrupt, residual-markup and non-letter-only rows. Remove exact
   duplicate **pairs**, not merely repeated English phrases. Record all removals.
6. Retain but flag identical-language text and extreme character-length ratios for
   review. These heuristics are not language identification or linguistic validation.
7. Refuse to publish fewer than 1,000 pairs; write only after all validations pass.

**Limitations:** verse-level alignment is not necessarily sentence-level translation
alignment. Sources can have omissions or versification differences. Native-speaker
review is still needed; no claim is made that every retained pair is linguistically
perfect. Bible text is religious and translation-style domain data, not representative
of everyday Ugandan speech. No train/dev/test splits are supplied: split by book or
chapter and audit repeated passages before evaluation to reduce leakage.

## Adding the pending languages

First verify the language's ISO code, translation identity, explicit verse IDs,
versification and permission to redistribute adaptations. Record the original
notice, source URL, revision and checksums. Then add a reviewed source adapter and
tests; do not simply change the Luganda path or label a related language as Acholi or
Ateso. The manifest in `sources/uganda.json` keeps those pending targets visible.
