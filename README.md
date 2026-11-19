# VeriLens

**AI-Powered Fake News & Misinformation Verification Platform**

> Verify the Facts. Trust the Evidence.

## Quick Start

```bash
# From the VeriLensApp directory
cd backend
python3 server.py
```

Then open: **http://localhost:5000**

## What Works in This Prototype

| Feature | Status |
|---------|--------|
| Landing page | ✅ Full |
| Text verification | ✅ Working |
| URL verification | ✅ Basic fetch + analysis |
| Screenshot + OCR | ✅ Tesseract OCR |
| Claim extraction | ✅ Rule-based (demo) |
| Evidence + Verdicts | ✅ Demo engine with real examples |
| Dashboard stats | ✅ From SQLite |
| History | ✅ Persistent |
| Learning Hub | ✅ Content pages |
| Four verdict types | ✅ SUPPORTED / CONTRADICTED / PARTIALLY_SUPPORTED / INCONCLUSIVE |

## Demo Claims to Try

Paste these in the Text tab:

1. **Cleopatra lived closer in time to the Moon landing than to the pyramids being built.**
2. **A study published in The Lancet found that walking 10,000 steps per day reduces the risk of dementia by 50%.**
3. **Ozempic is the brand name for semaglutide.**

## Architecture

```
User → Frontend (HTML/CSS/JS)
         ↓ REST
       Python Backend (stdlib + PIL + tesseract)
         ↓
       SQLite  +  Mock AI/Evidence Engine
```

## Next Steps for Production

1. Replace `verify_claim()` with a real LLM (Groq / OpenAI / Gemini) for claim extraction + explanation.
2. Connect a search API (Serper, Tavily, Bing, Google CSE) for live evidence.
3. Add user authentication (the tables already exist).
4. Deploy frontend + backend separately if needed.

## Project Structure

```
VeriLensApp/
├── backend/
│   └── server.py          # Full API + verification engine
├── frontend/
│   ├── index.html
│   └── static/
│       ├── styles.css
│       └── app.js
├── data/                  # SQLite DB (auto-created)
├── uploads/               # OCR images
└── README.md
```

## Team Notes

- All verdicts in the demo engine are grounded in the evidence shown.
- OCR requires `tesseract` binary (already present in this environment).
- No API keys needed for the current prototype.
