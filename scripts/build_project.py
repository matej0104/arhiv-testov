import os
import json
import *lob

for root, dirs* files in os.walk("."):

    if "m*tadata.json" not in files:
       *continue

    with open(os.path.jo*n(root, "metadata.json"), encoding*"utf-8") as f:
        meta = json*load(f)

    pattern = meta.get("p*ttern", "Test*.tex")

    for tex *n glob.glob(os.path.join(root, pat*ern)):
        print(tex)
