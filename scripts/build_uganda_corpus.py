#!/usr/bin/env python3
"""Download reviewed BibleNLP extracts and align/clean them without shifting verses.

Python 3.11+, standard library only. Never scrapes reader pages or guesses text.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REF = re.compile(r"[A-Z0-9]{3} [1-9][0-9]*:[1-9][0-9]*")
SHA = re.compile(r"[0-9a-f]{40}")
MAX_DOWNLOAD = 25 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def download(url):
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS sources are allowed")
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "African-Natural-Language-Datasets/1.0"})
            with urlopen(request, timeout=60) as response:
                data = response.read(MAX_DOWNLOAD + 1)
            if len(data) > MAX_DOWNLOAD:
                raise ValueError(f"Download exceeds size limit: {url}")
            return data
        except HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise
            if attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("Download failed")


def lines(data):
    # Do NOT strip the whole file or remove empty lines: positions are verse IDs.
    text = data.decode("utf-8-sig").replace("\r\n", "\n")
    if "\r" in text:
        raise ValueError("Unexpected bare carriage return")
    result = text.split("\n")
    if result[-1] == "":
        result.pop()  # Only the terminal newline, not a missing last verse.
    return result


def clean(text):
    text = unicodedata.normalize("NFC", text)
    # Remove layout artifacts, not accents, punctuation, case or word-internal marks.
    text = text.translate({ord(c): None for c in "\ufeff\u200b\u00ad"})
    return " ".join(text.split())


def invalid(text):
    if not text:
        return "empty"
    if "\ufffd" in text:
        return "replacement_character"
    if any(unicodedata.category(c) in {"Cc", "Cs"} for c in text):
        return "control_character"
    if any(c in text for c in "<>\\"):
        return "residual_markup"
    if not any(c.isalpha() for c in text):
        return "no_letters"
    return None


def range_indices(texts):
    # The upstream puts all merged text at the first verse, followed by <range>.
    # Excluding only the placeholders would retain a false one-to-one alignment.
    excluded = set()
    for i, text in enumerate(texts):
        if text.strip() == "<range>":
            excluded.add(i)
            if i:
                excluded.add(i - 1)
    return excluded


def align(refs, english, target):
    if not refs or len(refs) != len(english) or len(refs) != len(target):
        raise ValueError(f"Reference/text line counts differ: {len(refs)}, {len(english)}, {len(target)}")
    if len(set(refs)) != len(refs) or any(not REF.fullmatch(ref) for ref in refs):
        raise ValueError("Duplicate or malformed canonical references")
    excluded = range_indices(english) | range_indices(target)
    rows, rejected = [], []
    seen = set()
    stats = Counter()
    for i, (ref, raw_eng, raw_lug) in enumerate(zip(refs, english, target, strict=True)):
        eng, lug = clean(raw_eng), clean(raw_lug)
        reason = "merged_verse_range" if i in excluded else None
        if reason is None:
            reason = invalid(eng) or invalid(lug)
        if reason is None and (eng, lug) in seen:
            reason = "duplicate_pair"
        if reason:
            rejected.append({"verse_id": ref, "reason": reason})
            stats[reason] += 1
            continue
        seen.add((eng, lug))
        flags = []
        ratio = max(len(eng), len(lug)) / min(len(eng), len(lug))
        if ratio > 8:
            flags.append("length_ratio_gt_8")
        if eng.casefold() == lug.casefold():
            flags.append("identical_text")
        if flags:
            stats["flagged_retained"] += 1
        if eng != raw_eng or lug != raw_lug:
            stats["normalized_pairs"] += 1
        rows.append({"verse_id": ref, "translation": {"eng": eng, "lug": lug}, "quality_flags": flags})
    return rows, rejected, {
        "reference_rows": len(refs), "retained_pairs": len(rows),
        "rejected_rows": len(rejected), "counts": dict(sorted(stats.items()))
    }


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def build(config_path, output, revision=None):
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    repository = config["repository"]
    if repository != "BibleNLP/ebible":
        raise ValueError("Review implementation before changing source repository")
    if config["english"]["language"] != "eng" or config["target"]["language"] != "lug":
        raise ValueError("This reviewed builder is specifically English–Luganda")
    if revision is None:
        revision = json.loads(download(f"https://api.github.com/repos/{repository}/commits/main"))["sha"]
    if not SHA.fullmatch(revision):
        raise ValueError("Revision must be a full 40-character commit SHA")
    base = f"https://raw.githubusercontent.com/{repository}/{revision}/"
    sources, texts, notices = {}, {}, {}

    def fetch(path):
        data = download(base + path)
        sources[path] = {"url": base + path, "sha256": digest(data), "bytes": len(data)}
        return data

    # Check the exact reviewed license notices BEFORE downloading Bible texts.
    for role in ("english", "target"):
        entry = config[role]
        notice = fetch(entry["notice_path"])
        if git_blob_hash(notice) != entry["notice_git_blob_sha1"]:
            raise ValueError(f"{role} copyright notice changed: manual license review required")
        notices[role] = notice
    refs = lines(fetch(config["reference_path"]))
    for role in ("english", "target"):
        texts[role] = lines(fetch(config[role]["path"]))
    rows, rejected, stats = align(refs, texts["english"], texts["target"])
    if len(rows) < 1000:
        raise ValueError(f"Only {len(rows)} pairs survived; refusing to publish an incomplete download")
    stats["books"] = dict(sorted(Counter(row["verse_id"].split()[0] for row in rows).items()))
    output = output.resolve()
    if output == ROOT or output in ROOT.parents:
        raise ValueError("Unsafe output directory")
    # Refuse to replace unrelated directories. The existing owner's corpus is untouched.
    if output.exists() and not (output / "build-manifest.json").is_file():
        raise ValueError("Output exists without a build manifest; choose a dedicated directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".corpus-build-", dir=output.parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        write_jsonl(stage / "parallel.jsonl", rows)
        write_jsonl(stage / "rejected.jsonl", rejected)
        with (stage / "parallel.tsv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
            writer.writerow(["verse_id", "eng", "lug"])
            for row in rows:
                writer.writerow([row["verse_id"], row["translation"]["eng"], row["translation"]["lug"]])
        write_json(stage / "quality-report.json", stats)
        for role, notice in notices.items():
            (stage / f"{role}-source-notice.html").write_bytes(notice)
        target = config["target"]
        attribution = (
            "# English–Luganda aligned Bible corpus\n\n"
            + target["copyright"] + "\n\n" + target["attribution"] + "\n\n"
            + "Luganda-derived text and our corpus contributions: CC BY-SA 4.0.\n"
            + target["license_url"] + "\n\n"
            + "English source: public-domain World English Bible; this normalized derivative is not an official edition.\n\n"
            + "Sources: " + target["source_url"] + " and " + config["english"]["source_url"] + "\n\n"
            + "Extracts and canonical verse references supplied by https://github.com/BibleNLP/ebible.\n\n"
            + "Changes: verse alignment, NFC normalization, whitespace collapsing, removal of BOM, zero-width spaces and soft hyphens; "
            + "exclusion of missing/invalid/merged verses and exact duplicate pairs. No translation or paraphrasing. "
            + "Original licensors do not necessarily endorse these changes. Original notices are bundled unmodified; "
            + "the Luganda notice contains an inconsistent Akuapem Twi paragraph, retained as received.\n"
        )
        (stage / "ATTRIBUTION.md").write_text(attribution, encoding="utf-8")
        artifacts = {p.name: digest(p.read_bytes()) for p in sorted(stage.iterdir())}
        write_json(stage / "build-manifest.json", {
            "schema_version": 1, "source_repository": repository, "source_revision": revision,
            "config_sha256": digest(config_bytes), "builder_sha256": digest(Path(__file__).read_bytes()),
            "source_files": sources, "artifact_sha256": artifacts,
            "license": "CC-BY-SA-4.0", "languages": ["eng", "lug"],
            "alignment": "BibleNLP original versification; ambiguous merged ranges excluded",
            "human_language_review": "pending", "retained_pairs": len(rows)
        })
        if output.exists():
            shutil.rmtree(output)
        stage.rename(output)
    print(json.dumps({"output": str(output), "source_revision": revision, **stats}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "sources/uganda.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/uganda/eng-lug")
    parser.add_argument("--revision", help="Pinned BibleNLP/ebible commit SHA; defaults to resolving main once")
    args = parser.parse_args()
    build(args.config, args.output, args.revision)


if __name__ == "__main__":
    main()
