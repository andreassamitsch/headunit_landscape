from pathlib import Path

path = Path("scripts/apply_dudu7_13710_fm_favourites_stereo_af.py")
text = path.read_text(encoding="utf-8")
text = text.replace("identity_old = '''", "identity_old = r'''", 1)
text = text.replace("identity_new = '''", "identity_new = r'''", 1)
path.write_text(text, encoding="utf-8")
print("Corrected raw Kotlin persistence literals in 13.7.10 patch")
