# arhiv-testov

Arhiv kontrolnih nalog: **Overleaf → GitHub → Actions → PDF → WordPress → bot**.

## Struktura

```
arhiv-testov/
├── .github/workflows/
│   ├── sync-overleaf.yml     # klonira .tex iz Overleafa (cron / rocno / iz WordPressa)
│   └── build-pdf.yml         # prevede .tex → PDF in ustvari index.json
├── config/
│   └── projects.json         # seznam Overleaf projektov (ureja WordPress vticnik)
├── scripts/
│   ├── sync_overleaf.py      # Overleaf Git bridge → tex/
│   ├── build_project.py      # latexmk → pdf/
│   └── generate_index.py     # index.json za WordPress
├── index.json                # generirano
└── 2026_27/
    └── G3A/
        ├── metadata.json
        ├── tex/
        └── pdf/
```

## Nastavitev (enkratno)

### 1. Overleaf Git token

Overleaf → **Account Settings → Git Integration → Generate token**.
Zahteva placan racun (Git bridge ni na brezplacnem).

V GitHubu: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Vrednost |
|---|---|
| `OVERLEAF_TOKEN` | Overleaf git token |
| `WP_WEBHOOK_URL` | (neobvezno) `https://matej.info/wp-json/arhiv-testov/v1/webhook` |
| `WP_WEBHOOK_SECRET` | (neobvezno) isti niz kot v vticniku |

### 2. config/projects.json

Za vsak razred en vnos. `overleaf_url` je URL projekta iz brskalnika
(`https://www.overleaf.com/project/<id>`). Polja `school_year` in `class`
dolocata mapo v repozitoriju; ostala polja se zapisejo v `metadata.json`.

`pattern` doloca, katere datoteke iz projekta se prevedejo (npr. `Test*.tex`),
da se ne prevajajo pomozne `\input` datoteke.

To datoteko lahko urejas rocno ali preko WordPress vticnika.

### 3. Actions

- `sync-overleaf.yml` tece vsakih 30 minut, ob rocnem zagonu, ali ko ga
  sprozi WordPress vticnik (`repository_dispatch`, event `sync-overleaf`).
- Ce so se `.tex` datoteke spremenile, samodejno pozene `build-pdf.yml`.
- `build-pdf.yml` prevede samo spremenjene datoteke (`--force` prevede vse).

## Rocni zagon lokalno

```bash
export OVERLEAF_TOKEN=...
python scripts/sync_overleaf.py
python scripts/build_project.py          # ali --force
python scripts/generate_index.py
```

## index.json

WordPress vticnik bere `index.json`:

```json
{
  "generated": "2026-08-29T14:07:03+00:00",
  "count": 3,
  "items": [
    {
      "id": "2026-27-g3a-test-1-1",
      "school_year": "2026_27",
      "class": "G3A",
      "subject": "Matematika",
      "teacher": "Matej Mlakar",
      "collection": "Kontrolne naloge G3A",
      "tags": ["2026_27", "G3A"],
      "name": "Test.1.1",
      "title": "Kontrolna naloga 1.1",
      "tex": "2026_27/G3A/tex/Test.1.1.tex",
      "pdf": "2026_27/G3A/pdf/Test.1.1.pdf",
      "has_pdf": true,
      "tex_sha": "b2de64f369bc",
      "pdf_sha": "668c217f293d",
      "pdf_size": 31887,
      "updated": "2026-08-29T14:06:59+00:00"
    }
  ]
}
```

`pdf_sha` omogoca vticniku, da prenese samo spremenjene PDF-je.
`public: false` v `metadata.json` izloci cel razred iz `index.json`.
