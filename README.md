# True Capability Validator 🎯

> **Eightfold AI × Techkriti'26 Hackathon**

An intelligent web platform that combats LLM-generated, spam, and embellished resumes by cross-referencing claims against verifiable external data.

## What It Does

1. **Upload** a resume (PDF)
2. **Extracts** profile URLs (GitHub, Codeforces, LinkedIn, Kaggle, etc.)
3. **Scrapes** public data from those profiles via APIs
4. **Searches** the web for the candidate's digital footprint
5. **Cross-references** resume claims against scraped evidence
6. **Detects** AI-generated content in the resume text
7. **Generates** a True Capability Report with confidence-scored verifications

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your API keys (GITHUB_TOKEN, GEMINI_API_KEY)

# 4. Run the server
uvicorn app.main:app --reload --port 8000

# 5. Open http://localhost:8000 in your browser
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python 3.11+ |
| PDF Parsing | pdfplumber + PyMuPDF + pytesseract |
| NLP | spaCy + regex |
| Scraping | GitHub API, Codeforces API, httpx |
| Web Search | DuckDuckGo |
| LLM | Google Gemini API |
| AI Detection | Statistical heuristics |
| Database | SQLite (aiosqlite) |
| Frontend | Jinja2 + HTMX + Vanilla CSS |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Upload page |
| `POST` | `/api/upload` | Upload a resume PDF |
| `GET` | `/api/status/{job_id}` | Check analysis status |
| `GET` | `/api/report/{job_id}` | Get report as JSON |
| `GET` | `/api/report/{job_id}/view` | View report as HTML |
| `GET` | `/health` | Health check |

## Project Structure

```
app/
├── main.py                 # FastAPI entry point
├── config.py               # Environment-based settings
├── database.py             # SQLite setup
├── models/schemas.py       # Pydantic data models
├── services/
│   ├── pdf_parser.py       # PDF text extraction
│   ├── entity_extractor.py # URL/skill/entity extraction
│   ├── scrapers/           # Platform-specific scrapers
│   ├── web_search.py       # DuckDuckGo fallback
│   ├── cross_reference.py  # Claim verification engine
│   ├── ai_detector.py      # AI text detection
│   └── report_generator.py # Report builder
├── routers/                # API endpoints
├── templates/              # Jinja2 HTML templates
└── static/                 # CSS & JavaScript
```
