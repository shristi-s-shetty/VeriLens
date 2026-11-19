#!/usr/bin/env python3
"""
VeriLens Backend - AI-Powered Fake News & Misinformation Detector
Pure Python (stdlib + requests + PIL + tesseract)
"""

import json
import os
import sqlite3
import hashlib
import uuid
import re
import time
import base64
import io
import urllib.request
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("Warning: OCR not fully available")

# ============== CONFIG ==============
PORT = 5000
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "verilens.db"
UPLOAD_DIR = BASE_DIR / "uploads"
FRONTEND_DIR = BASE_DIR / "frontend"

UPLOAD_DIR.mkdir(exist_ok=True)
(BASE_DIR / "data").mkdir(exist_ok=True)

# ============== DATABASE ==============
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            input_type TEXT NOT NULL,
            original_input TEXT,
            extracted_text TEXT,
            status TEXT DEFAULT 'completed',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS claims (
            id TEXT PRIMARY KEY,
            analysis_id TEXT NOT NULL,
            claim_text TEXT NOT NULL,
            verdict TEXT NOT NULL,
            confidence REAL,
            explanation TEXT,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        );
        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL,
            source_name TEXT,
            source_url TEXT,
            evidence_summary TEXT,
            evidence_type TEXT,
            published_at TEXT,
            relevance REAL,
            FOREIGN KEY (claim_id) REFERENCES claims(id)
        );
        CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY,
            analysis_id TEXT,
            claim_preview TEXT,
            verdict TEXT,
            input_type TEXT,
            created_at TEXT
        );
    """)
    conn.commit()
    conn.close()
    print("Database initialized.")

# ============== MOCK AI ENGINE ==============
# In production: replace with real LLM API (OpenAI, Groq, Gemini, etc.)

KNOWN_CLAIMS = {
    "cleopatra lived closer to the moon landing than to the pyramids": {
        "verdict": "SUPPORTED",
        "confidence": 0.92,
        "explanation": "Cleopatra VII lived around 30 BC. The Great Pyramid was built around 2560 BC (about 2,530 years earlier). The Moon landing was in 1969 AD (about 1,999 years after Cleopatra). Therefore the claim is factually correct.",
        "supporting": [
            {"source": "Britannica", "url": "https://www.britannica.com/biography/Cleopatra-queen-of-Egypt", "summary": "Cleopatra VII reigned 51–30 BC.", "date": "2024"},
            {"source": "Smithsonian", "url": "https://www.si.edu/spotlight/ancient-egypt/pyramids", "summary": "Great Pyramid of Giza constructed c. 2560 BC.", "date": "2023"},
            {"source": "NASA", "url": "https://www.nasa.gov/mission_pages/apollo/missions/apollo11.html", "summary": "Apollo 11 Moon landing: July 20, 1969.", "date": "2019"},
        ],
        "contradicting": []
    },
    "walking 10000 steps reduces dementia risk by 50%": {
        "verdict": "PARTIALLY_SUPPORTED",
        "confidence": 0.78,
        "explanation": "Multiple studies show that higher daily step counts are associated with lower dementia risk. A 2022 Lancet Public Health study found that accumulating more steps was linked to reduced risk, with benefits around 9,800 steps. However, the exact '50%' figure and causal language overstate the evidence; the relationship is associative.",
        "supporting": [
            {"source": "The Lancet Public Health", "url": "https://www.thelancet.com/journals/lanpub/article/PIIS2468-2667(22)00163-0/fulltext", "summary": "2022 study: higher daily steps associated with lower dementia incidence.", "date": "2022"},
            {"source": "Alzheimer's Association", "url": "https://www.alz.org", "summary": "Physical activity is a modifiable risk factor for cognitive decline.", "date": "2023"},
        ],
        "contradicting": [
            {"source": "Context note", "url": "", "summary": "Most studies show association, not proven causation at exactly 50%.", "date": "2024"}
        ]
    },
    "ozempic is the brand name for semaglutide": {
        "verdict": "SUPPORTED",
        "confidence": 0.98,
        "explanation": "Ozempic is a brand name of semaglutide, a GLP-1 receptor agonist developed by Novo Nordisk, approved for type 2 diabetes. Wegovy is another brand of the same molecule used for weight management.",
        "supporting": [
            {"source": "FDA", "url": "https://www.fda.gov", "summary": "Ozempic (semaglutide) approved for type 2 diabetes.", "date": "2017"},
            {"source": "Novo Nordisk", "url": "https://www.novonordisk.com", "summary": "Ozempic is the brand name for semaglutide injection.", "date": "2024"},
        ],
        "contradicting": []
    },
}

def extract_claims(text: str) -> list:
    """Simple claim extraction. In production use LLM with structured output."""
    text = text.strip()
    if not text:
        return []

    # Split into sentences roughly
    sentences = re.split(r'(?<=[.!?])\s+', text)
    claims = []
    for s in sentences:
        s = s.strip()
        if len(s) > 25 and not s.lower().startswith(("http", "www", "the following")):
            # Filter out questions and pure opinions for MVP
            if not s.endswith("?"):
                claims.append(s)
    if not claims and text:
        claims = [text[:500]]
    return claims[:5]  # limit for demo

def verify_claim(claim_text: str) -> dict:
    """Mock verification engine. Replace with real search + LLM in production."""
    claim_lower = claim_text.lower()

    # Check against known examples
    for key, data in KNOWN_CLAIMS.items():
        if key in claim_lower or any(w in claim_lower for w in key.split()[:4]):
            return {
                "claim_text": claim_text,
                "verdict": data["verdict"],
                "confidence": data["confidence"],
                "explanation": data["explanation"],
                "supporting": data["supporting"],
                "contradicting": data["contradicting"],
            }

    # Heuristic fallback
    if any(w in claim_lower for w in ["proven", "100%", "always", "never", "cure", "miracle"]):
        return {
            "claim_text": claim_text,
            "verdict": "INCONCLUSIVE",
            "confidence": 0.45,
            "explanation": "This claim uses absolute or medical language that typically requires strong primary sources. Available public evidence is insufficient for a firm verdict in this prototype.",
            "supporting": [],
            "contradicting": [],
        }

    return {
        "claim_text": claim_text,
        "verdict": "INCONCLUSIVE",
        "confidence": 0.40,
        "explanation": "In this prototype version, the evidence engine could not locate sufficiently strong public sources to support or contradict the claim with high confidence. A production system would query live search APIs and rank sources by credibility.",
        "supporting": [
            {"source": "Prototype Note", "url": "", "summary": "Live search API not connected in this offline demo.", "date": datetime.now().strftime("%Y")}
        ],
        "contradicting": []
    }

def run_verification(input_type: str, content: str, extracted: str = None) -> dict:
    """Full verification pipeline."""
    text = extracted or content
    claims_raw = extract_claims(text)
    verified_claims = []

    for c in claims_raw:
        result = verify_claim(c)
        verified_claims.append(result)

    analysis_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    # Persist
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO analyses (id, user_id, input_type, original_input, extracted_text, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (analysis_id, None, input_type, content[:2000], (extracted or content)[:2000], "completed", now)
    )

    for vc in verified_claims:
        claim_id = str(uuid.uuid4())
        c.execute(
            "INSERT INTO claims (id, analysis_id, claim_text, verdict, confidence, explanation) VALUES (?,?,?,?,?,?)",
            (claim_id, analysis_id, vc["claim_text"], vc["verdict"], vc["confidence"], vc["explanation"])
        )
        for ev in vc.get("supporting", []) + vc.get("contradicting", []):
            etype = "supporting" if ev in vc.get("supporting", []) else "contradicting"
            c.execute(
                "INSERT INTO evidence (id, claim_id, source_name, source_url, evidence_summary, evidence_type, published_at, relevance) VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), claim_id, ev.get("source"), ev.get("url"), ev.get("summary"), etype, ev.get("date"), 0.8)
            )

    # History entry
    preview = verified_claims[0]["claim_text"][:120] if verified_claims else content[:120]
    verdict = verified_claims[0]["verdict"] if verified_claims else "INCONCLUSIVE"
    c.execute(
        "INSERT INTO history (id, analysis_id, claim_preview, verdict, input_type, created_at) VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4()), analysis_id, preview, verdict, input_type, now)
    )
    conn.commit()
    conn.close()

    return {
        "analysis_id": analysis_id,
        "input_type": input_type,
        "original_input": content[:500],
        "extracted_text": extracted,
        "claims": verified_claims,
        "created_at": now,
        "status": "completed"
    }

# ============== HTTP HANDLER ==============
class VeriLensHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, content, status=200):
        body = content.encode("utf-8") if isinstance(content, str) else content
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str):
        if not path.exists():
            self._json({"error": "Not found"}, 404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self._cors()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        # API routes
        if path == "/api/health":
            self._json({"status": "ok", "service": "VeriLens", "ocr": OCR_AVAILABLE})
            return

        if path == "/api/dashboard/stats":
            conn = get_db()
            c = conn.cursor()
            total = c.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
            claims = c.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
            recent = c.execute("SELECT * FROM history ORDER BY created_at DESC LIMIT 8").fetchall()
            conn.close()
            self._json({
                "total_analyses": total,
                "total_claims": claims,
                "recent": [dict(r) for r in recent]
            })
            return

        if path == "/api/history":
            conn = get_db()
            c = conn.cursor()
            rows = c.execute("SELECT * FROM history ORDER BY created_at DESC LIMIT 50").fetchall()
            conn.close()
            self._json({"history": [dict(r) for r in rows]})
            return

        if path.startswith("/api/analysis/"):
            aid = path.split("/")[-1]
            conn = get_db()
            c = conn.cursor()
            analysis = c.execute("SELECT * FROM analyses WHERE id=?", (aid,)).fetchone()
            if not analysis:
                self._json({"error": "Not found"}, 404)
                return
            claims = c.execute("SELECT * FROM claims WHERE analysis_id=?", (aid,)).fetchall()
            result_claims = []
            for cl in claims:
                ev = c.execute("SELECT * FROM evidence WHERE claim_id=?", (cl["id"],)).fetchall()
                supporting = [dict(e) for e in ev if e["evidence_type"] == "supporting"]
                contradicting = [dict(e) for e in ev if e["evidence_type"] == "contradicting"]
                result_claims.append({
                    "claim_text": cl["claim_text"],
                    "verdict": cl["verdict"],
                    "confidence": cl["confidence"],
                    "explanation": cl["explanation"],
                    "supporting": supporting,
                    "contradicting": contradicting,
                })
            conn.close()
            self._json({
                "analysis_id": analysis["id"],
                "input_type": analysis["input_type"],
                "original_input": analysis["original_input"],
                "extracted_text": analysis["extracted_text"],
                "claims": result_claims,
                "created_at": analysis["created_at"],
                "status": analysis["status"]
            })
            return

        # Static / frontend
        if path == "/" or path == "/index.html":
            self._file(FRONTEND_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            fpath = FRONTEND_DIR / path[1:]
            if fpath.suffix == ".css":
                self._file(fpath, "text/css")
            elif fpath.suffix == ".js":
                self._file(fpath, "application/javascript")
            else:
                self._file(fpath, "application/octet-stream")
            return

        # SPA fallback
        self._file(FRONTEND_DIR / "index.html", "text/html; charset=utf-8")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            data = {}

        if path == "/api/verify/text":
            text = (data.get("text") or "").strip()
            if not text or len(text) < 10:
                self._json({"error": "Please provide a claim or text of at least 10 characters."}, 400)
                return
            result = run_verification("text", text)
            self._json(result)
            return

        if path == "/api/verify/url":
            url = (data.get("url") or "").strip()
            if not url.startswith("http"):
                self._json({"error": "Please provide a valid http/https URL."}, 400)
                return
            # Simple fetch (limited)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "VeriLens/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                # Very rough text extraction
                text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
                text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()[:3000]
                if len(text) < 50:
                    text = f"Could not extract meaningful article text from {url}. Treating the URL itself as the claim context."
            except Exception as e:
                text = f"Unable to retrieve content from the URL ({str(e)[:80]}). Please paste the article text instead."
            result = run_verification("url", url, extracted=text)
            self._json(result)
            return

        if path == "/api/verify/image":
            # Expect base64 image
            b64 = data.get("image") or ""
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            if not b64:
                self._json({"error": "No image data provided."}, 400)
                return
            try:
                img_bytes = base64.b64decode(b64)
                img = Image.open(io.BytesIO(img_bytes))
                # Save for debug
                fname = UPLOAD_DIR / f"{uuid.uuid4().hex}.png"
                img.save(fname)
                if OCR_AVAILABLE:
                    extracted = pytesseract.image_to_string(img)
                    extracted = extracted.strip()
                else:
                    extracted = "[OCR engine not available in this environment]"
                if not extracted or len(extracted) < 5:
                    extracted = "No readable text could be extracted from the image."
            except Exception as e:
                self._json({"error": f"Image processing failed: {str(e)[:100]}"}, 400)
                return
            result = run_verification("image", f"[Screenshot upload]", extracted=extracted)
            self._json(result)
            return

        self._json({"error": "Unknown endpoint"}, 404)

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    init_db()
    server = ThreadedHTTPServer(("0.0.0.0", PORT), VeriLensHandler)
    print(f"""
╔══════════════════════════════════════════════════╗
║           VERILENS BACKEND RUNNING               ║
║                                                  ║
║   http://localhost:{PORT}                          ║
║   API:  /api/health  /api/verify/text            ║
║         /api/verify/url  /api/verify/image       ║
║         /api/dashboard/stats  /api/history       ║
╚══════════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
