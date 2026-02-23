# Legal Agent - Product Definition

## Problem

Lawyers and legal decision-makers in Vietnam need to reference similar past cases when working on current cases. These are high-stakes decisions — imprisonment, death penalty — and having past cases to reference is critical for building arguments and making fair judgments.

Vietnam is a **civil law** country — lawyers primarily argue from statutes and legal codes, not binding precedent. However, court judgments show **how courts have interpreted and applied specific laws in practice**, which is highly valuable. Vietnam also has an official "án lệ" (precedent) system since 2015, where the Supreme People's Court selects specific cases as reference precedents.

Currently there is no affordable tool that lets Vietnamese lawyers search 36,000+ court judgments by factual similarity.

## Solution

A search tool where a lawyer inputs their case facts and gets back similar past cases — ranked by relevance — with full details: findings, court reasoning, verdict, and legal articles applied.

## Users

Vietnamese lawyers and legal decision-makers working on court cases (criminal, civil, commercial, administrative).

## Core User Flow

```
Lawyer has a case
  → Inputs case facts/situation (free text, Vietnamese)
  → System searches 36,000 cases by semantic similarity on NỘI DUNG VỤ ÁN
  → Optionally applies filters: case type, court level, date range
  → Returns ranked list of similar cases
  → Each result shows:
     - Case number & date
     - Court name
     - Case type
     - Summary of facts (NỘI DUNG VỤ ÁN)
     - Court's reasoning (NHẬN ĐỊNH CỦA TÒA ÁN)
     - Verdict & sentence (QUYẾT ĐỊNH)
     - Legal articles cited
  → Lawyer clicks to view full case detail (all 4 sections)
```

## Data

- **Source**: 36,000 Vietnamese court judgments (Kaggle dataset, provided by Vietnamese authorities)
- **Format**: PDF files
  - ~40% digital text (direct extraction)
  - ~60% scanned images (need OCR)
- **Size**: 38.3 GB total
- **Language**: Vietnamese

## Vietnamese Court Judgment Structure

Every Vietnamese court judgment (bản án) follows a standardized format with 4 sections:

| # | Section | Header in PDF | Contains |
|---|---------|--------------|----------|
| 1 | Opening | *(no explicit header — top of document)* | Court name, case number, date, trial panel, parties, lawyers, procedural info |
| 2 | Case Content | **NỘI DUNG VỤ ÁN:** | What the parties claim/present, evidence, first-instance verdict (if appellate) |
| 3 | Court's Analysis | **NHẬN ĐỊNH CỦA TÒA ÁN:** | Court's reasoning — numbered points evaluating evidence and applying specific legal articles |
| 4 | Decision | **QUYẾT ĐỊNH:** | Verdict, specific legal articles applied (Điều X Bộ luật Y), sentence, court fees, appeal rights |

**What matters most for search:**
- **NỘI DUNG VỤ ÁN** contains the case facts — this is what we embed for semantic similarity search
- **NHẬN ĐỊNH CỦA TÒA ÁN** contains the court's legal reasoning — the most valuable content for lawyers to read
- **QUYẾT ĐỊNH** contains the verdict, legal articles applied, and sentence

**Note:** The dataset contains mixed case types (criminal, civil, commercial, administrative), not only criminal cases.

## How Search Works

Lawyer inputs their case situation as free text → system embeds it → finds cases with the most similar facts (from NỘI DUNG VỤ ÁN section) using vector similarity.

Optional filters:
- Case type (loại vụ án)
- Court level (sơ thẩm/phúc thẩm)
- Date range

The approach:
1. Extract text from all 36,000 PDFs
2. Split each case into the 4 sections using headers: NỘI DUNG VỤ ÁN, NHẬN ĐỊNH CỦA TÒA ÁN, QUYẾT ĐỊNH
3. Extract structured fields: case number, date, court, legal articles cited
4. Generate vector embeddings from NỘI DUNG VỤ ÁN (facts) for semantic search

## Data Processing Pipeline

### Step 1: Text Extraction
- Digital PDFs (40%): **PyMuPDF** — fast, free, direct text extraction
- Scanned PDFs (60%): **Surya OCR** — open source, strong Vietnamese support, runs on GPU

### Step 2: Structure Parsing
Split raw text into 4 sections using the standard headers (NỘI DUNG VỤ ÁN, NHẬN ĐỊNH CỦA TÒA ÁN, QUYẾT ĐỊNH) and extract structured fields. Use **regex** for section splitting (headers are consistent), **Gemini 2.0 Flash** (free tier: 1,500 requests/day) for complex extraction:
- From **opening** (text before NỘI DUNG VỤ ÁN): case number, date, court, case type, trial level, parties
- From **NỘI DUNG VỤ ÁN**: full case facts text
- From **NHẬN ĐỊNH CỦA TÒA ÁN**: full court reasoning text + legal articles cited
- From **QUYẾT ĐỊNH**: verdict, outcome, legal articles applied, court fees

### Step 3: Embedding & Indexing
- Embed **NỘI DUNG VỤ ÁN** (facts) using **multilingual-e5-large** (free, runs locally, 560M params) for semantic search
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

## Service Architecture

### Development Flow (offline, on dev machine — 24GB RAM, 6GB GPU)

Batch processing pipeline that runs once to prepare the data:

```
36,000 PDFs
  → Auto-detect digital vs scanned
  → Digital (40%): PyMuPDF extracts text directly
  → Scanned (60%): Surya OCR extracts text using GPU
  → Raw text for all cases
  → Regex splits into 4 sections (headers: NỘI DUNG VỤ ÁN, NHẬN ĐỊNH CỦA TÒA ÁN, QUYẾT ĐỊNH)
  → Gemini 2.0 Flash extracts structured fields from opening section
  → multilingual-e5-large generates vector embeddings from NỘI DUNG VỤ ÁN (facts)
  → Structured data + vectors loaded into PostgreSQL + pgvector
  → Database exported and transferred to home server
```

Key constraints:
- OCR (Surya) requires GPU — only runs on dev machine
- Embedding generation (multilingual-e5-large, 560M params) requires GPU
- Gemini free tier: 1,500 requests/day — mitigate with regex for standard sections, LLM only for complex cases
- This pipeline runs once (or re-runs when new cases are added)

### Inference Flow (online, on home server — 8GB RAM, no GPU)

What happens when a lawyer searches:

```
Lawyer inputs case situation (Vietnamese free text)
  → FastAPI sends text to embedding service (multilingual-e5-large on CPU)
  → Query vector compared against NỘI DUNG VỤ ÁN vectors (pgvector cosine similarity)
  → Apply filters (case type, court level, date)
  → Return top-N ranked results with: case number, date, court, facts summary, verdict, articles cited
  → Lawyer clicks a result → full case detail (all 4 sections)
```

Key constraints:
- No GPU on server — embedding model runs on CPU (slower but acceptable for single queries)
- 8GB RAM must fit: PostgreSQL + pgvector + FastAPI + embedding model + Caddy + React static files
- pgvector handles 36,000 vectors efficiently at this scale

