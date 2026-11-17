"""
Builds resume_profiles.json from the PDFs in resumes/ (skill names only, never contact info).
Runs automatically whenever the PDFs change; you never need to run it yourself.
Name files so they contain DA, DE or DS, e.g. Resume_DA.pdf.
"""
import hashlib
import json
import re
from pathlib import Path

from skills import find_skills

HERE = Path(__file__).parent
RESUME_DIR = HERE / "resumes"
PROFILE_FILE = HERE / "resume_profiles.json"


def _pdf_text(path):
    from pypdf import PdfReader
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    # drop contact lines; "BU Spark!" is a program name, not the Spark tool
    text = "\n".join(l for l in text.splitlines() if "@" not in l)
    return text.replace("Spark!", "")


def _label(path):
    m = re.search(r"(?<![A-Za-z])(DA|DE|DS)(?![A-Za-z])", path.stem.replace("_", " ").replace("-", " "))
    return m.group(1) if m else path.stem


def refresh_profiles():
    """Rebuild profiles if resumes/ has PDFs that changed since the last build."""
    pdfs = sorted(RESUME_DIR.glob("*.pdf")) if RESUME_DIR.exists() else []
    if not pdfs:
        return False
    digest = hashlib.sha256(b"".join(p.read_bytes() for p in pdfs)).hexdigest()
    try:
        if json.loads(PROFILE_FILE.read_text()).get("_hash") == digest:
            return False
    except Exception:
        pass
    profiles = {_label(p): sorted(find_skills(_pdf_text(p))) for p in pdfs}
    PROFILE_FILE.write_text(json.dumps(
        {"_note": "Auto-built from resumes/ (skill names only).", "_hash": digest, "resumes": profiles}, indent=1))
    print("Resumes changed -> rebuilt skill profiles:", ", ".join(f"{k} ({len(v)} skills)" for k, v in profiles.items()))
    return True


if __name__ == "__main__":
    refresh_profiles() or print("Profiles already up to date")
