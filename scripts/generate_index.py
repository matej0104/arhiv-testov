import os
import json
import glob

results = []

for root, dirs, files in os.walk("."):

    if "metadata.json" not in files:
        continue

    meta_file = os.path.join(root, "metadata.json")

    try:
        with open(meta_file, encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        print(f"Napaka pri branju {meta_file}: {e}")
        continue

    pattern = meta.get("pattern", "*.tex")

    tex_files = glob.glob(os.path.join(root, pattern))

    for tex in tex_files:

        name = os.path.splitext(os.path.basename(tex))[0]

        results.append({
            "school_year": meta.get("school_year"),
            "class": meta.get("class"),
            "subject": meta.get("subject"),
            "teacher": meta.get("teacher"),
            "tags": meta.get("tags", []),
            "title": name,
            "tex": tex.replace("\\", "/"),
            "pdf": f"PDFs/{meta.get('school_year')}/{meta.get('class')}/{name}.pdf"
        })

with open("index.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Ustvarjenih zapisov: {len(results)}")
