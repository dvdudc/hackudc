# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-03-01
### Added
- **Query Intent Routing**: Replaced raw SQL generation with a Pydantic-based intent parser (`intent.py`) for safe, parameterized SQL construction.
- **Metadata Vectorization**: Added a new `item_embeddings` table to store dense vectors of each item's tags and summary.
- **Session Context**: Introduced `session_history` table to track recently viewed items and provide dynamic score boosts to search results aligned with user context.
- **Controlled Query Expansion**: The LLM now extracts a `lexical_synonyms` field to enhance BM25 FTS recall without contaminating the semantic HNSW query.
- **Temporal Bypass**: Queries that are purely metadata/temporal (e.g. "archivos de hoy") bypass the hybrid search entirely and perform a direct SQL `SELECT` sorted by date.

### Fixed
- Fixed `TypeError` in `lex_score` when FTS found no matches.
- Scoring bugs fixed: Temporal bypass now uses a 7-day recency decay instead of a static `1.0` placeholder.
- **BM25 Search Penalty**: Added penalty for very short or untitled snippets that artificially inflated BM25 scores.
- Increased minimum score threshold to `0.1` to strip out low-quality or negative-score results from the search output.

## [0.2.0] - 2026-02-28
### Added
- Working CLI Search pipeline with hybrid semantic (HNSW via DuckDB+VSS) and lexical (BM25 FTS) strategies at a 70/30 weighting.
- LLM Enrichment via Ollama (`llama3.2`) to extract tags, titles, and summaries from raw files.
- Command-line interface with `ingest`, `logstart`, `search`, `list`, `show`, and `export` commands via Typer and Rich.
- Ingestion pipeline chunking with `langchain-text-splitters` and type filtering with `python-magic`.
- Fast `gemini-embedding-001` usage via Gemini API.
