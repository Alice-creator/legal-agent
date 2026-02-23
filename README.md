# Legal Agent

A semantic search tool for Vietnamese court judgments. Lawyers input their case facts and get back similar past cases — ranked by relevance — from a database of 36,000+ court judgments.

## How it works

1. Lawyer inputs case facts (free text, Vietnamese)
2. System embeds the query and searches by vector similarity against the NỘI DUNG VỤ ÁN (case content) section of all cases
3. Returns ranked similar cases with: facts, court reasoning, verdict, and legal articles applied

## Tech stack

| Layer | Technology |
|-------|-----------|
| OCR | Surya |
| Text extraction | PyMuPDF |
| Structure parsing | Gemini 2.0 Flash API |
| Embeddings | multilingual-e5-large |
| Database | PostgreSQL + pgvector |
| Backend | Python FastAPI |
| Frontend | React (Vite) |
| Reverse proxy | Caddy |

## Documentation

- [Product Definition](docs/product_decision.md)
