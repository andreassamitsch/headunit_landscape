from pathlib import Path
import base64
import zlib

root = Path(__file__).resolve().parents[1]
parts = root / "scripts" / "patches"
payload = "".join((parts / f"issues_111_116.part{i}").read_text(encoding="utf-8").strip() for i in range(3))
source = zlib.decompress(base64.b64decode(payload)).decode("utf-8")
exec(compile(source, "issues_111_116_embedded.py", "exec"), {"__file__": str(root / "scripts" / "issues_111_116_embedded.py")})
