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

    tex_files = glob.glob(*s.path.join(root, pattern))

    p*f_dir = os.path.join(
        "PDF*",
        meta["school_year"],
  *     meta["class"]
    )

    os.m*kedirs(pdf_dir, exist_ok=True)

  * for tex in tex_files:

        pr*nt("Prevajam:", tex)

        subp*ocess.run([
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            tex
        ])

        pdf_sour*e = os.path.splitext(tex)[0] + ".p*f"

        if os.path.exists(pdf_*ource):

            pdf_target = *s.path.join(
                pdf_d*r,
                os.path.basenam*(pdf_source)
            )

      *     os.replace(pdf_source, pdf_ta*get)
