# Legal Agent - Product Definition

## Problem

Lawyers and legal decision-makers in Vietnam need to reference similar past cases when working on current cases. These are high-stakes decisions — imprisonment, death penalty — and having precedent cases to reference is critical for building arguments and making fair judgments.

Currently there is no affordable tool that lets Vietnamese lawyers search 36,000+ court judgments by situation/facts similarity.

## Solution

A search tool where a lawyer inputs their current case situation and gets back similar past cases — ranked by relevance — with full details: facts, verdict, sentence, legal articles cited.

## Users

Vietnamese lawyers and legal decision-makers working on criminal cases.

## Core User Flow

```
Lawyer has a case
  → Inputs case facts/situation (free text, Vietnamese)
  → System searches 36,000 cases by semantic similarity
  → Returns ranked list of similar cases
  → Each result shows:
     - Case number & date
     - Court name
     - Case type
     - Summary of facts
     - Court's reasoning
     - Verdict & sentence
     - Legal articles cited
  → Lawyer clicks to view full case detail
```

## Data

- **Source**: 36,000 Vietnamese court judgments (Kaggle dataset, provided by Vietnamese authorities)
- **Format**: PDF files
  - ~40% digital text (direct extraction)
  - ~60% scanned images (need OCR)
- **Size**: 38.3 GB total
- **Language**: Vietnamese
- **Structure**: Standard Vietnamese court judgment format with consistent sections:
  - Header: court name, case number, date, case type
  - Parties: plaintiff, defendant, representatives, lawyers
  - Nội dung vụ án: case facts
  - Nhận định của Tòa án: court's legal reasoning
  - Quyết định: verdict/decision
  - Legal articles cited (Điều/Bộ luật references)

## How Similarity Search Works

"Similar case" = similar **facts/situation** (Nội dung vụ án section).

The approach:
1. Extract text from all 36,000 PDFs
2. Parse each case into structured fields (case number, date, court, facts, reasoning, verdict, articles)
3. Generate vector embeddings from the case facts
4. When lawyer inputs their case situation → embed it → find nearest vectors → return those cases

Supplementary filters:
- Case type (loại vụ án)
- Court level (sơ thẩm/phúc thẩm)
- Legal articles cited (Điều X Bộ luật Y)
- Date range

## Data Processing Pipeline

### Step 1: Text Extraction
- Digital PDFs (40%): **PyMuPDF** — fast, free, direct text extraction
- Scanned PDFs (60%): **Surya OCR** — open source, strong Vietnamese support, runs on GPU

### Step 2: Structure Parsing
Use **Gemini 2.0 Flash** (free tier: 1,500 requests/day) to parse raw text into structured JSON:
```json
{
  "case_number": "25/2022/KDTM-PT",
  "date": "2022-08-18",
  "court": "Tòa án nhân dân thành phố Đà Nẵng",
  "case_type": "Tranh chấp Hợp đồng kinh doanh hạ tầng Cụm Công nghiệp",
  "trial_level": "phúc thẩm",
  "plaintiff": "Công ty Cổ phần Đầu tư Đ-M",
  "defendant": "Công ty TNHH T",
  "facts": "...(full Nội dung vụ án text)...",
  "reasoning": "...(full Nhận định của Tòa án text)...",
  "verdict": "...(full Quyết định text)...",
  "articles_cited": ["Điều 30 BLTTDS", "Điều 46 Luật Doanh nghiệp 2020", ...],
  "outcome": "Không chấp nhận kháng cáo"
}
```

### Step 3: Embedding & Indexing
- Embed the `facts` field using **multilingual-e5-large** (free, runs locally, 560M params)
- Store structured data + vectors in **PostgreSQL + pgvector**

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| OCR | Surya | Free, open source, strong Vietnamese, runs on 6GB GPU |
| Text extraction | PyMuPDF | Free, fast, reliable for digital PDFs |
| Structure parsing | Gemini 2.0 Flash API | Free tier (1,500 req/day), good at Vietnamese |
| Embeddings | multilingual-e5-large | Free, multilingual, runs locally |
| Database | PostgreSQL + pgvector | Free, handles both structured data + vector search |
| Backend | Python FastAPI | Lightweight, async, low memory footprint |
| Frontend | React (Vite, static build) | Developer already knows React, serves as static files |
| Reverse proxy | Caddy | Simple, auto-HTTPS, lightweight |
| OS | Alpine Linux | Minimal footprint for 8GB server |

**Total cost: $0**

## Infrastructure

### Development machine (processing)
- 24 GB RAM, 6 GB GPU
- Used for: OCR processing, embedding generation, development
- Not running 24/7

### Home server (production)
- 8 GB RAM, 512 GB SSD, no GPU
- Runs: PostgreSQL + FastAPI + static React files + Caddy
- Runs 24/7 on Alpine Linux

## Timeline (1 month)

### Week 1: Data processing pipeline
- Build PDF text extraction (PyMuPDF for digital, Surya for scanned)
- Auto-detect digital vs scanned PDFs
- Process all 36,000 PDFs → raw text
- Estimated: ~3-4 days for OCR processing on dev machine

### Week 2: Structuring & indexing
- Build Gemini Flash parser to extract structured fields from raw text
- Process all cases (1,500/day free tier = ~24 days... need strategy)
  - Option A: Use local LLM (Qwen 2.5 7B) for bulk, Gemini for validation
  - Option B: Regex + rules for standard sections, Gemini for complex cases only
  - Option C: Mix — regex for headers/articles, LLM for facts summarization
- Generate embeddings for all cases
- Load into PostgreSQL + pgvector

### Week 3: Search backend
- FastAPI with search endpoints
- Semantic search (vector similarity on case facts)
- Structured filters (case type, court, date, articles)
- Result ranking and pagination

### Week 4: Frontend & deployment
- React search interface
- Case detail view (full judgment display)
- Deploy to home server (Alpine + Docker)
- Testing with real queries

## Key Risk: Week 2 bottleneck

At 1,500 free Gemini requests/day, processing 36,000 cases takes 24 days. Mitigation:
- Vietnamese court judgments have a **very consistent format**
- Use **regex/rule-based parsing** for standard sections (header, parties, verdict)
- Only use LLM for the complex parts (facts summarization, outcome classification)
- This reduces LLM calls significantly — possibly to a few thousand edge cases

## MVP Scope (what we build in 1 month)

### In scope
- Full-text search by case situation (semantic similarity)
- Structured filters (case type, court level, date range, articles cited)
- Case detail view with all sections
- Basic responsive UI

### Out of scope (future)
- User accounts / authentication
- Case bookmarking / notes
- Export / print functionality
- API for third-party integration
- Mobile app
- Multi-language support
