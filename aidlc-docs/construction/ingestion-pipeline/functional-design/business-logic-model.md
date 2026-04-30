# Business Logic Model — ingestion-pipeline

**Fecha**: 2026-04-29 (v2 — deterministic extraction + ENV support)

---

## Pipeline Flow

```
ENV Resolution (BR-12)
    │ INGESTION_ENV=local  → StorageProvider=Filesystem, EmbeddingsProvider=Ollama
    │ INGESTION_ENV=prod   → StorageProvider=S3, EmbeddingsProvider=Bedrock
    ▼
StorageProvider.list_brochures()  →  [pdf_path_or_key, ...]
StorageProvider.get_object(path)  →  pdf_bytes
    ▼
PDFParser.parse(pdf_bytes, course_name)     [DETERMINISTIC — no LLM]
    │ pdfplumber → raw text
    │ Regex header detection (BR-04)
    │ Apply BR-01: 12 BrochureSection per PDF
    ▼
Filter: BrochureSection where present=True AND content != ""   (BR-02)
    ▼
KeywordsExtractor.extract_keywords(sections)   [cheap LLM — BR-10]
    │ Per section: call Ollama/Haiku with keywords prompt
    │ Attach keywords to each section
    │ BR-09: 3 retries with backoff on LLM failure
    │ On total failure: keywords=[] (chunk is NOT discarded)
    ▼
EmbeddingGenerator.generate(sections)
    │ Per section:
    │   text = enrich(course_name, section_type, content)   (BR-05)
    │   embedding = EmbeddingsProvider.embed(text)          (Ollama local / Bedrock prod)
    │   id = f"{course_name}_{section_type}"                (BR-03)
    │   keywords = section.keywords[:10]                    (BR-08)
    │ → list[EmbeddedChunk]
    ▼
VectorDBRepository.upsert(chunks)
    │ Upsert idempotente por chunk.id
    ▼
ReportRepository.save(report)   (BR-11)
    │ LOCAL: write JSON to reports/{timestamp}.json
    │ PROD:  upload JSON to S3 reports/{timestamp}.json
    ▼
IngestionReport
```

---

## IngestionOrchestrator — Algoritmo Principal

```python
def run(config: IngestionConfig) -> IngestionReport:
    report = IngestionReport(env=config.env, timestamp=now_iso(), ...)
    pdf_entries = storage_provider.list_brochures()
    report.total_pdfs = len(pdf_entries)

    for entry in pdf_entries:
        course_name = stem(entry)   # filename without extension
        try:
            pdf_bytes = storage_provider.get_object(entry)

            sections = pdf_parser.parse(pdf_bytes, course_name)
            # → 12 BrochureSection, applying BR-01

            present_sections = [s for s in sections if s.present and s.content]
            # Applying BR-02

            present_sections = keywords_extractor.extract_keywords(present_sections)
            # Applying BR-10, BR-09

            chunks = embedding_generator.generate(present_sections)
            # → list[EmbeddedChunk], applying BR-03, BR-05, BR-08

            vector_db.upsert(chunks)

            report.processed += 1
            report.total_chunks_upserted += len(chunks)
            report.total_sections_extracted += len(present_sections)

        except Exception as e:
            # BR-06: error in one PDF does NOT stop the pipeline
            report.failed += 1
            report.errors.append(IngestionError(
                course_name=course_name,
                step=detect_step(e),   # "parse" | "keywords" | "embedding" | "upsert"
                message=str(e)
            ))

    report.duration_seconds = elapsed()
    report_repository.save(report)   # BR-11
    return report
```

---

## PDFParser — Algoritmo Determinístico

```python
def parse(pdf_bytes: bytes, course_name: str) -> list[BrochureSection]:
    raw_text = pdfplumber_extract_text(pdf_bytes)
    normalized = normalize_whitespace(raw_text)

    sections: dict[SectionType, BrochureSection] = {
        st: BrochureSection(course_name=course_name, section_type=st,
                            content="", present=False)
        for st in SectionType
    }

    # Detect all header positions
    matches: list[tuple[int, SectionType]] = []
    for section_type, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            m = re.search(pattern, normalized, re.IGNORECASE)
            if m:
                matches.append((m.start(), section_type))
                break  # first matching pattern wins

    matches.sort(key=lambda x: x[0])

    # Extract content between consecutive headers
    for i, (start_pos, section_type) in enumerate(matches):
        end_pos = matches[i + 1][0] if i + 1 < len(matches) else len(normalized)
        content = normalized[start_pos:end_pos].strip()
        # Remove the header line itself
        content = strip_header_line(content)
        if content:
            sections[section_type].content = content
            sections[section_type].present = True

    return list(sections.values())   # always 12 items
```

---

## KeywordsExtractor — Algoritmo

```python
def extract_keywords(sections: list[BrochureSection]) -> list[BrochureSection]:
    for section in sections:
        for attempt in range(1, 4):   # BR-09: up to 3 retries
            try:
                response = llm_provider.complete(
                    prompt=KEYWORDS_PROMPT.format(content=section.content),
                    model=config.keywords_model   # Haiku (prod) / Ollama model (local)
                )
                section.keywords = parse_json_list(response)[:10]   # BR-08
                break
            except (LLMError, JSONParseError) as e:
                if attempt == 3:
                    section.keywords = []   # BR-09: don't discard chunk on failure
                    log_warning(f"keywords failed for {section.course_name}/{section.section_type}: {e}")
                else:
                    sleep(2 ** (attempt - 1))   # backoff: 1s, 2s
    return sections
```

---

## EmbeddingGenerator — Algoritmo

```python
def generate(sections: list[BrochureSection]) -> list[EmbeddedChunk]:
    chunks = []
    for section in sections:
        enriched_text = (
            f"Programa: {section.course_name}\n"
            f"Sección: {section.section_type.value}\n\n"
            f"{section.content}"
        )  # BR-05

        embedding = embeddings_provider.embed(enriched_text)
        # LOCAL:  Ollama (e.g. nomic-embed-text)
        # PROD:   Bedrock (e.g. amazon.titan-embed-text-v2:0)

        chunk = EmbeddedChunk(
            id=f"{section.course_name}_{section.section_type.value}",   # BR-03
            course_name=section.course_name,
            section_type=section.section_type,
            content=section.content,
            embedding=embedding,
            keywords=section.keywords[:10]   # BR-08
        )
        chunks.append(chunk)
    return chunks
```

---

## StorageProvider — Variantes por ENV

```python
# LOCAL
class FilesystemStorageProvider:
    def list_brochures(self) -> list[Path]:
        return list(Path(config.local_knowledge_dir).glob("*.pdf"))

    def get_object(self, path: Path) -> bytes:
        return path.read_bytes()

# PRODUCTION
class S3StorageProvider:
    def list_brochures(self) -> list[str]:
        return s3_client.list_objects_v2(Bucket=config.s3_bucket, Prefix=config.s3_prefix)

    def get_object(self, key: str) -> bytes:
        return s3_client.get_object(Bucket=config.s3_bucket, Key=key)["Body"].read()
```

---

## ReportRepository — Variantes por ENV

```python
# LOCAL
class FilesystemReportRepository:
    def save(self, report: IngestionReport) -> None:
        path = Path(config.local_reports_dir) / f"report_{report.timestamp}.json"
        path.write_text(json.dumps(asdict(report), indent=2))

# PRODUCTION
class S3ReportRepository:
    def save(self, report: IngestionReport) -> None:
        key = f"{config.s3_reports_prefix}/report_{report.timestamp}.json"
        s3_client.put_object(
            Bucket=config.s3_bucket,
            Key=key,
            Body=json.dumps(asdict(report), indent=2)
        )
```

---

## Interfaces de Entrada/Salida

| Componente | Input | Output |
|---|---|---|
| `IngestionOrchestrator.run` | `IngestionConfig` | `IngestionReport` |
| `PDFParser.parse` | `pdf_bytes: bytes`, `course_name: str` | `list[BrochureSection]` (12 items) |
| `KeywordsExtractor.extract_keywords` | `list[BrochureSection]` | `list[BrochureSection]` (con keywords) |
| `EmbeddingGenerator.generate` | `list[BrochureSection]` (solo presentes) | `list[EmbeddedChunk]` |
| `VectorDBRepository.upsert` | `list[EmbeddedChunk]` | `None` |
| `StorageProvider.list_brochures` | — | `list[Path \| str]` |
| `StorageProvider.get_object` | `path \| key` | `bytes` |
| `ReportRepository.save` | `IngestionReport` | `None` |
