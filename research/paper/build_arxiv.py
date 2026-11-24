"""Build arxiv_upload.zip: main.tex (bibliography inlined) + figs/*.pdf.

    python figures.py && python bib2tex.py && python build_arxiv.py

Refuses to build while the text still contains \\TBD{...} placeholders.
"""

import re
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    tex = (HERE / "main.tex").read_text(encoding="utf8")
    todo = re.findall(r"\\TBD\{([^}]*)\}", tex)
    if todo:
        raise SystemExit("not ready, open placeholders:\n  " + "\n  ".join(todo))
    figs = sorted(set(re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", tex)))
    out = HERE / "arxiv_upload.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("main.tex", tex)
        for f in figs:
            z.write(HERE / "figs" / f"{f}.pdf", f"figs/{f}.pdf")
    print(f"{out.name}: main.tex + {len(figs)} figures")


if __name__ == "__main__":
    main()
