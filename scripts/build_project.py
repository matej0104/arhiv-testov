#!/usr/bin/env python3
"""
Prevede vse .tex datoteke v repozitoriju v PDF.

Struktura, ki jo pricakuje:

    <school_year>/<class>/
        metadata.json      <- vsebuje "pattern" (npr. "Test*.tex")
        tex/               <- izvorne .tex datoteke (in slike)
        pdf/               <- rezultat (ustvari se sam)

Ce mape tex/ ni, se .tex datoteke iscejo kar poleg metadata.json
(zdruzljivost s staro strukturo).

Uporaba:
    python scripts/build_project.py            # prevede samo spremenjeno
    python scripts/build_project.py --force    # prevede vse
    python scripts/build_project.py --only 2026_27/G3A
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".github", "scripts", "config", "node_modules"}


def log(msg):
    print(msg, flush=True)


def find_projects(root):
    """Vrne seznam map, ki vsebujejo metadata.json."""
    projects = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if "metadata.json" in filenames:
            projects.append(Path(dirpath))
    return sorted(projects)


def load_metadata(project_dir):
    meta_file = project_dir / "metadata.json"
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        log(f"  OPOZORILO: ne morem prebrati {meta_file}: {exc}")
        return {}


def source_dir(project_dir):
    tex_dir = project_dir / "tex"
    return tex_dir if tex_dir.is_dir() else project_dir


def needs_build(tex_file, pdf_file, src_dir):
    """PDF je zastarel, ce ga ni ali je starejsi od katerekoli izvorne datoteke."""
    if not pdf_file.exists():
        return True
    pdf_mtime = pdf_file.stat().st_mtime
    if tex_file.stat().st_mtime > pdf_mtime:
        return True
    # slike, .sty, vkljucene datoteke ...
    for path in src_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() != ".pdf":
            if path.stat().st_mtime > pdf_mtime:
                return True
    return False


def compile_tex(tex_file, src_dir, build_dir, pdf_dir):
    """Prevede eno .tex datoteko. Vrne pot do PDF-ja ali None."""
    build_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "latexmk",
        "-pdf",
        "-file-line-error",
        "-interaction=nonstopmode",
        f"-outdir={build_dir}",
        tex_file.name,
    ]

    proc = subprocess.run(
        cmd,
        cwd=src_dir,
        capture_output=True,
        text=True,
    )

    produced = build_dir / (tex_file.stem + ".pdf")

    if not produced.exists():
        log(f"    NAPAKA pri prevajanju {tex_file.name} (koda {proc.returncode})")
        tail = (proc.stdout or "").strip().splitlines()[-25:]
        for line in tail:
            log(f"      | {line}")
        return None

    if proc.returncode != 0:
        log(f"    OPOZORILO: latexmk je vrnil {proc.returncode}, PDF vseeno nastal.")

    target = pdf_dir / produced.name
    shutil.copy2(produced, target)
    return target


def clean_orphans(pdf_dir, expected_names):
    """Odstrani PDF-je, katerih .tex izvora ni vec."""
    if not pdf_dir.is_dir():
        return []
    removed = []
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        if pdf.name not in expected_names:
            pdf.unlink()
            removed.append(pdf.name)
    return removed


def build_project(project_dir, force=False):
    meta = load_metadata(project_dir)
    pattern = meta.get("pattern", "*.tex")

    src_dir = source_dir(project_dir)
    pdf_dir = project_dir / "pdf"
    build_dir = project_dir / ".build"

    tex_files = sorted(src_dir.glob(pattern))
    rel = project_dir.relative_to(REPO_ROOT)

    if not tex_files:
        log(f"[{rel}] ni .tex datotek za vzorec {pattern!r} v {src_dir.name}/")
        return 0, 0

    log(f"[{rel}] {len(tex_files)} datotek (vzorec {pattern!r})")

    built = 0
    failed = 0
    expected = set()

    for tex in tex_files:
        pdf_target = pdf_dir / (tex.stem + ".pdf")
        expected.add(pdf_target.name)

        if not force and not needs_build(tex, pdf_target, src_dir):
            log(f"    aktualen: {tex.name}")
            continue

        log(f"    prevajam: {tex.name}")
        result = compile_tex(tex, src_dir, build_dir, pdf_dir)
        if result:
            built += 1
        else:
            failed += 1

    for name in clean_orphans(pdf_dir, expected):
        log(f"    odstranjen zastarel PDF: {name}")

    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    return built, failed


def main():
    parser = argparse.ArgumentParser(description="Prevedi vse .tex projekte v PDF.")
    parser.add_argument("--force", action="store_true", help="Prevedi tudi ze aktualne datoteke.")
    parser.add_argument("--only", help="Samo ta projekt, npr. 2026_27/G3A")
    parser.add_argument("--root", default=str(REPO_ROOT), help="Korenska mapa repozitorija.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    projects = find_projects(root)

    if args.only:
        wanted = (root / args.only).resolve()
        projects = [p for p in projects if p.resolve() == wanted]
        if not projects:
            log(f"NAPAKA: projekt {args.only!r} nima metadata.json.")
            return 1

    if not projects:
        log("Ni najdenih projektov (metadata.json).")
        return 0

    total_built = 0
    total_failed = 0

    for project_dir in projects:
        built, failed = build_project(project_dir, force=args.force)
        total_built += built
        total_failed += failed

    log(f"\nPrevedeno: {total_built} PDF, napak: {total_failed}")
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
