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

    tex_files = glob.glob(*s.path.join(root, pattern))

    f*r tex in tex_files:

        name * os.path.splitext(os.path.basename*tex))[0]

        pdf_path = os.pa*h.join(root, "pdf", f"{name}.pdf")*
        results.append({
        *   "school_year": meta.get("school*year"),
            "class": meta.*et("class"),
            "subject"* meta.get("subject"),
            *teacher": meta.get("teacher"),
   *        "tags": meta.get("tags", []),
            "title": name,
    *       "tex": tex.replace("\\", "/*),
            "pdf": pdf_path.rep*ace("\\", "/")
        })

results*sort(
    key=lambda x: (
        *.get("school_year", ""),
        x*get("class", ""),
        x.get("t*tle", "")
    )
)

with open("inde*.json", "w", encoding="utf-8") as *:
    json.dump(results, f, ensure*ascii=False, indent=2)

print(f"Us*varjenih zapisov: {len(results)}")*
