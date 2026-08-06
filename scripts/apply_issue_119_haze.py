from pathlib import Path
import base64
import zlib

ROOT = Path(__file__).resolve().parents[1]
parts = sorted((ROOT / "scripts" / "patches" / "issue_119_haze").glob("part_*.txt"))
if not parts:
    raise RuntimeError("Issue 119 Haze patch payload is missing")
payload = "".join(part.read_text().strip() for part in parts)
source = zlib.decompress(base64.b64decode(payload)).decode("utf-8")
code = compile(source, "apply_issue_119_haze_payload.py", "exec")
exec(code, {"__name__": "__main__", "__file__": str(ROOT / "scripts" / "apply_issue_119_haze.py")})
