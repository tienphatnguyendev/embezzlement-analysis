"""List every hex colour in the given files and flag any not in the Deloitte colour guide (Feb 2026).
Usage: python check_colours.py <file or folder> [...]   (works on .py, .ipynb, .html, .css, .json)"""
import pathlib, re, sys
GUIDE = set("""#86BC25 #0DF200 #3C8F2A #046A38 #1C3D26 #F1F6E4 #000000 #222222 #E6E6E6 #FFFFFF
#009A44 #43B02A #C4D600 #E3E48D #0D8390 #004F59 #007680 #0097A9 #00ABAB #6FC2B4 #9DD4CF #DDEFE8
#041E42 #012169 #005587 #0076A8 #00A3E0 #62B5E5 #A0DCFF #53565A #63666A #75787B #97999B #A7A8AA
#BBBCBC #D0D0CE #3EFAC5 #33F0FF #DA291C #ED8B00 #FFCD00""".split())
files = [p for a in sys.argv[1:] for p in (pathlib.Path(a).rglob("*") if pathlib.Path(a).is_dir() else [pathlib.Path(a)])
         if p.suffix in {".py", ".ipynb", ".html", ".css", ".json", ".md"}]
bad = {}
for f in files:
    for h in re.findall(r"#[0-9A-Fa-f]{6}\b", f.read_text(errors="ignore")):
        if h.upper() not in GUIDE:
            bad.setdefault(h.upper(), set()).add(str(f))
for h, fs in sorted(bad.items()):
    print(f"NOT IN GUIDE {h}: {', '.join(sorted(fs))}")
print("PASS: every colour is in the Deloitte guide" if not bad else f"FAIL: {len(bad)} colour(s) outside the guide")
sys.exit(1 if bad else 0)
