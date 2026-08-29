#!/usr/bin/env python3
"""
Ustvari index.json - seznam vseh nalog v arhivu.

Datoteko bere WordPress vticnik, da ve, katere PDF-je naj prenese in prikaze.

Uporaba:
    python scripts/generate_index.py
"""

import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "index.json"
SKIP_DIRS = {".git", ".github", "scripts", "config", "node_modules"}

TITLE_RE = re.compile(r"\\title\s*\{(.+?)\}", re.DOTALL)


def log(msg):
    print(msg, flush=True)


def slugify(value):
    value = unicodedata.normalize("NFKD", str(value))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "x"


def sha1_of(path, limit=None):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    digest = h.hexdigest()
    return digest[:limit] if limit else digest


def find_projects(root):
    projects = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if "metadata.json" in filenames:
            projects.append(Path(dirpath))
    return sorted(projects)


def source_dir(project_dir):
    tex_dir = project_dir / "tex"
    return tex_dir if tex_dir.is_dir() else project_dir


def extract_title(tex_path):
    try:
        text = tex_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = TITLE_RE.search(text)
    if not m:
        return None
    title = m.group(1)
    title = re.sub(r"\\\\|\\newline", " ", title)
    title = re.sub(r"\\[a-zA-Z]+\s*", "", title)
    title = re.sub(r"[{}]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or None


def rel(path):
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def main():
    entries = []
    projects = find_projects(REPO_ROOT)

    for project_dir in projects:
        meta_file = project_dir / "metadata.json"
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            log(f"Napaka pri branju {rel(meta_file)}: {exc}")
            continue

        if meta.get("public") is False:
            log(f"Preskoceno (public=false): {rel(project_dir)}")
            continue

        pattern = meta.get("pattern", "*.tex")
        src_dir = source_dir(project_dir)
        pdf_dir = project_dir / "pdf"

        for tex in sorted(src_dir.glob(pattern)):
            name = tex.stem
            pdf_path = pdf_dir / f"{name}.pdf"

            entry = {
                "id": "-".join(filter(None, [
                    slugify(meta.get("school_year", "")),
                    slugify(meta.get("class", "")),
                    slugify(name),
                ])),
                "school_year": meta.get("school_year"),
                "class": meta.get("class"),
                "subject": meta.get("subject"),
                "teacher": meta.get("teacher"),
                "collection": meta.get("title"),
                "tags": meta.get("tags", []),
                "name": name,
                # Naslov je ime datoteke iz projekta (Test.1.1), ker Overleaf
                # v \title{} zapise ime projekta in to ni naslov naloge.
                "title": name,
                # LaTeX \title{} obdrzimo za kontekst bota.
                "doc_title": extract_title(tex),
                "tex": rel(tex),
                "pdf": rel(pdf_path) if pdf_path.exists() else None,
                "has_pdf": pdf_path.exists(),
                "tex_sha": sha1_of(tex, 12),
                "pdf_sha": sha1_of(pdf_path, 12) if pdf_path.exists() else None,
                "pdf_size": pdf_path.stat().st_size if pdf_path.exists() else None,
                "updated": datetime.fromtimestamp(
                    tex.stat().st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds"),
            }
            entries.append(entry)

    entries.sort(key=lambda x: (
        x.get("school_year") or "",
        x.get("class") or "",
        x.get("name") or "",
    ))

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(entries),
        "items": entries,
    }

    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    missing = [e["name"] for e in entries if not e["has_pdf"]]
    log(f"Ustvarjenih zapisov: {len(entries)} -> {rel(OUTPUT)}")
    if missing:
        log(f"Brez PDF-ja ({len(missing)}): {', '.join(missing[:10])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
