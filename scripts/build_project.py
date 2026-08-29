import os
import json
import glob
import subprocess

for root, dirs, files in os.walk("."):

    if "metadata.json" not in files:
        continue

    with open(os.path.join(root, "metadata.json"), encoding="utf-8") as f:
        meta = json.load(f)

    pattern = meta.get("pattern", "*.tex")

    tex_files = glob.glob(os.path.join(root, pattern))

    pdf_dir = os.path.join(root, "pdf")

    os.makedirs(pdf_dir, exist_ok=True)

    for tex in tex_files:

        print("Prevajam:", tex)

        subprocess.run(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                tex
            ],
            check=True
        )

        pdf_source = os.path.splitext(tex)[0] + ".pdf"

        if os.path.exists(pdf_source):

            pdf_target = os.path.join(
                pdf_dir,
                os.path.basename(pdf_source)
            )

            os.replace(pdf_source, pdf_target)

            print("Shranjen:", pdf_target)
