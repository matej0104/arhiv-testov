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

Kdaj se datoteka prevaja:

  * PDF-ja ni  -> vedno (tudi ce se je prejsnji poskus koncal z napako)
  * vsebina .tex se je spremenila glede na zadnji uspesen prevod
  * spremenila se je katera od pomoznih datotek (slike, .sty, .cls ...)
  * z zastavico --force

Primerjamo vsebino (SHA-256), ne casov spreminjanja: GitHub Actions ob
prenosu repozitorija vsem datotekam nastavi enak cas, zato je primerjava
casov v CI neuporabna.

Uporaba:
    python scripts/build_project.py            # prevede samo potrebno
    python scripts/build_project.py --force    # prevede vse
    python scripts/build_project.py --strict   # neuspeh vrne izhodno kodo 1
    python scripts/build_project.py --only 2026_27/G3A
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".github", "scripts", "config", "node_modules"}

MANIFEST_NAME = ".build-manifest.json"


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- pomozno


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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


# ------------------------------------------------------------- manifest


def manifest_path(pdf_dir):
    return pdf_dir / MANIFEST_NAME


def load_manifest(pdf_dir):
    path = manifest_path(pdf_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save_manifest(pdf_dir, manifest):
    pdf_dir.mkdir(parents=True, exist_ok=True)
    manifest_path(pdf_dir).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def deps_hash(src_dir, tex_file, siblings=frozenset()):
    """
    Skupni odtis pomoznih datotek (slike, .sty, .cls, vkljucene .tex).

    Druge glavne datoteke testov (siblings) izpustimo -- vsaka se prevaja
    zase, zato sprememba enega testa ne sme sprozati prevoda vseh ostalih.
    """
    h = hashlib.sha256()
    for path in sorted(src_dir.rglob("*")):
        if not path.is_file():
            continue
        if path == tex_file or path in siblings:
            continue
        if path.suffix.lower() == ".pdf":
            continue
        h.update(str(path.relative_to(src_dir)).encode("utf-8"))
        h.update(sha256_of(path).encode("ascii"))
    return h.hexdigest()


def needs_build(tex_file, pdf_file, src_dir, manifest, force=False, siblings=frozenset()):
    """Vrne (ali_prevajamo, razlog)."""
    if force:
        return True, "zahtevan ponoven prevod"

    # Kljucno: brez PDF-ja vedno poskusimo znova. Tako se datoteka, ki se
    # prejsnjic ni prevedla, ob naslednjem zagonu spet prevaja.
    if not pdf_file.exists():
        return True, "PDF ne obstaja"

    entry = manifest.get(tex_file.name)
    if not isinstance(entry, dict):
        return True, "ni zapisa o prejsnjem prevodu"

    if entry.get("tex") != sha256_of(tex_file):
        return True, "vsebina .tex se je spremenila"

    if entry.get("deps") != deps_hash(src_dir, tex_file, siblings):
        return True, "spremenila se je pomozna datoteka"

    return False, "aktualen"


# ------------------------------------------------------------ prevajanje


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
        for line in (proc.stdout or "").strip().splitlines()[-25:]:
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
        return 0, []

    log(f"[{rel}] {len(tex_files)} datotek (vzorec {pattern!r})")

    manifest = load_manifest(pdf_dir)
    siblings = frozenset(tex_files)
    built = 0
    failed = []
    expected = set()
    manifest_changed = False

    for tex in tex_files:
        pdf_target = pdf_dir / (tex.stem + ".pdf")
        expected.add(pdf_target.name)

        build, reason = needs_build(tex, pdf_target, src_dir, manifest, force, siblings)

        if not build:
            log(f"    aktualen: {tex.name}")
            continue

        log(f"    prevajam: {tex.name} ({reason})")
        result = compile_tex(tex, src_dir, build_dir, pdf_dir)

        if result:
            built += 1
            manifest[tex.name] = {
                "tex": sha256_of(tex),
                "deps": deps_hash(src_dir, tex, siblings),
            }
            manifest_changed = True
        else:
            failed.append(str(rel / tex.name))
            # Zapis odstranimo, da se ob naslednjem zagonu spet poskusi.
            if tex.name in manifest:
                del manifest[tex.name]
                manifest_changed = True

    for name in clean_orphans(pdf_dir, expected):
        log(f"    odstranjen zastarel PDF: {name}")

    # Iz manifesta pobrisemo datoteke, ki jih ni vec.
    stale = [key for key in manifest if key not in {t.name for t in tex_files}]
    for key in stale:
        del manifest[key]
        manifest_changed = True

    if manifest_changed or not manifest_path(pdf_dir).exists():
        save_manifest(pdf_dir, manifest)

    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    return built, failed


def main():
    parser = argparse.ArgumentParser(description="Prevedi vse .tex projekte v PDF.")
    parser.add_argument("--force", action="store_true", help="Prevedi tudi ze aktualne datoteke.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Ob neuspelem prevodu vrni izhodno kodo 1 (privzeto vrne 0, "
             "da se uspesno prevedeni PDF-ji vseeno objavijo).",
    )
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
    all_failed = []

    for project_dir in projects:
        built, failed = build_project(project_dir, force=args.force)
        total_built += built
        all_failed.extend(failed)

    log(f"\nPrevedeno: {total_built} PDF, neuspelih: {len(all_failed)}")

    if all_failed:
        log("\nNeuspeli prevodi (na strani se ne bodo prikazali):")
        for name in all_failed:
            log(f"  - {name}")
        log("\nPopravi .tex, znova nalozi ZIP in prevajanje bo poskusilo samodejno.")

    # Privzeto ne rusimo zagona: en pokvarjen .tex ne sme prepreciti
    # objave vseh ostalih PDF-jev.
    return 1 if (all_failed and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
