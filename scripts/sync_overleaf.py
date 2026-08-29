#!/usr/bin/env python3
"""
Sinhronizacija Overleaf -> GitHub.

Prebere config/projects.json, za vsak omogocen projekt klonira Overleaf Git
bridge repozitorij in prekopira izvorne datoteke v:

    <school_year>/<class>/tex/

ter zapise / posodobi <school_year>/<class>/metadata.json.

Avtentikacija: Overleaf Git token (Account Settings -> Git integration).
Token pricakuje v okoljski spremenljivki OVERLEAF_TOKEN.

Uporaba:
    python scripts/sync_overleaf.py
    python scripts/sync_overleaf.py --only 2026_27-G3A
    python scripts/sync_overleaf.py --dry-run
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "projects.json"

# Datoteke, ki jih prenesemo iz Overleafa (izvorne datoteke projekta).
COPY_SUFFIXES = {
    ".tex", ".sty", ".cls", ".bib", ".bst",
    ".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg",
    ".csv", ".dat", ".txt",
}

# Mape, ki jih nikoli ne kopiramo.
SKIP_DIRS = {".git", ".github", "_minted", "auto"}

METADATA_KEYS = [
    "class", "school_year", "subject", "pattern",
    "tags", "teacher", "title", "public",
]


def log(msg):
    print(msg, flush=True)


def extract_project_id(url):
    """Iz Overleaf URL-ja izlusci ID projekta."""
    url = (url or "").strip()
    if not url:
        return None
    # https://www.overleaf.com/project/<id>  |  /read/<token> ni podprt za git
    m = re.search(r"/project/([0-9a-fA-F]{16,32})", url)
    if m:
        return m.group(1)
    # ce je uporabnik vpisal samo ID
    m = re.fullmatch(r"[0-9a-fA-F]{16,32}", url)
    if m:
        return m.group(0)
    # https://git.overleaf.com/<id>
    m = re.search(r"git\.overleaf\.com/([0-9a-fA-F]{16,32})", url)
    if m:
        return m.group(1)
    return None


def run_git(args, cwd=None, token=None):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        stderr = proc.stderr
        if token:
            stderr = stderr.replace(token, "***")
        raise RuntimeError(f"git {' '.join(args)} -> {proc.returncode}\n{stderr}")
    return proc.stdout


def clone_project(project_id, token, dest):
    url = f"https://git:{token}@git.overleaf.com/{project_id}"
    run_git(["clone", "--depth", "1", url, str(dest)], token=token)


def copy_sources(src_dir, dst_dir, dry_run=False):
    """Prekopira izvorne datoteke iz klona v tex/ mapo. Vrne (dodani, odstranjeni)."""
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)

    wanted = {}
    for path in src_dir.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src_dir)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() not in COPY_SUFFIXES:
            continue
        wanted[rel] = path

    if not dry_run:
        dst_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for rel, src in sorted(wanted.items()):
        dst = dst_dir / rel
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        written.append(str(rel))

    # Odstrani datoteke, ki jih v Overleafu ni vec.
    removed = []
    if dst_dir.exists():
        for path in sorted(dst_dir.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(dst_dir)
            if rel not in wanted:
                removed.append(str(rel))
                if not dry_run:
                    path.unlink()

    return written, removed


def write_metadata(project, target_dir, dry_run=False):
    meta_path = Path(target_dir) / "metadata.json"

    existing = {}
    if meta_path.exists():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    meta = dict(existing)
    for key in METADATA_KEYS:
        if key in project and project[key] not in (None, ""):
            meta[key] = project[key]

    meta.setdefault("pattern", "*.tex")
    meta.setdefault("public", True)

    payload = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"

    if meta_path.exists() and meta_path.read_text(encoding="utf-8") == payload:
        return False

    if not dry_run:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(payload, encoding="utf-8")
    return True


def sync_project(project, token, dry_run=False):
    pid = extract_project_id(project.get("overleaf_url"))
    if not pid:
        raise ValueError(
            f"Neveljaven overleaf_url: {project.get('overleaf_url')!r}"
        )

    school_year = project.get("school_year")
    klass = project.get("class")
    if not school_year or not klass:
        raise ValueError("Projekt mora imeti 'school_year' in 'class'.")

    target_dir = REPO_ROOT / school_year / klass
    tex_dir = target_dir / "tex"

    log(f"  Overleaf projekt {pid} -> {school_year}/{klass}/tex/")

    if dry_run and not token:
        log("    (dry-run brez tokena: samo preverjanje konfiguracije)")
        return 0, 0, False

    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "overleaf"
        clone_project(pid, token, clone_dir)
        written, removed = copy_sources(clone_dir, tex_dir, dry_run=dry_run)

    meta_changed = write_metadata(project, target_dir, dry_run=dry_run)

    log(f"    datoteke: {len(written)} kopiranih, {len(removed)} odstranjenih"
        f"{', metadata posodobljena' if meta_changed else ''}")
    for rel in removed:
        log(f"    - odstranjeno: {rel}")

    return len(written), len(removed), meta_changed


def main():
    parser = argparse.ArgumentParser(description="Sinhroniziraj Overleaf projekte v repozitorij.")
    parser.add_argument("--only", help="Sinhroniziraj samo projekt s tem 'id'.")
    parser.add_argument("--dry-run", action="store_true", help="Samo izpisi, ne zapisuj.")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Pot do projects.json.")
    args = parser.parse_args()

    token = os.environ.get("OVERLEAF_TOKEN", "").strip()
    if not token and not args.dry_run:
        log("NAPAKA: manjka okoljska spremenljivka OVERLEAF_TOKEN.")
        return 1

    config_path = Path(args.config)
    if not config_path.exists():
        log(f"NAPAKA: ni datoteke {config_path}")
        return 1

    config = json.loads(config_path.read_text(encoding="utf-8"))
    projects = config.get("projects", [])

    if args.only:
        projects = [p for p in projects if p.get("id") == args.only]
        if not projects:
            log(f"NAPAKA: projekt z id={args.only!r} ne obstaja.")
            return 1

    failures = 0
    synced = 0

    for project in projects:
        pid = project.get("id") or project.get("class") or "?"
        if not project.get("enabled", True):
            log(f"[preskoceno] {pid} (enabled=false)")
            continue

        # Razredi, ki se uvazajo prek ZIP-a iz WordPressa, nimajo Overleaf URL-ja.
        if not (project.get("overleaf_url") or "").strip():
            log(f"[preskoceno] {pid} (brez overleaf_url - uvoz prek ZIP)")
            continue

        log(f"[sync] {pid}")
        try:
            sync_project(project, token, dry_run=args.dry_run)
            synced += 1
        except Exception as exc:  # noqa: BLE001
            failures += 1
            log(f"  NAPAKA: {exc}")

    log(f"\nKoncano: {synced} projektov sinhroniziranih, {failures} napak.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
