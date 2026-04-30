# Business Rules — ingestion-pipeline

**Fecha**: 2026-04-29 (v2 — deterministic extraction + ENV support)

---

## BR-01: Extracción de secciones completa

**Regla**: El parser DEBE intentar extraer las 12 secciones de cada PDF, independientemente de si existen en el documento.

**Aplicación**:
- Si una sección no existe en el PDF, `BrochureSection.present = False` y `content = ""`
- El parser siempre produce exactamente 12 `BrochureSection` por archivo

**Rationale**: Garantiza schema consistente entre todos los brochures.

---

## BR-02: Solo secciones presentes generan chunks

**Regla**: Solo las secciones con `present=True` y `content` no vacío generan `EmbeddedChunk` y se almacenan en el Vector DB.

**Aplicación**:
- `EmbeddingGenerator` filtra secciones con `present=False` antes de generar embeddings

---

## BR-03: ID de chunk determinístico

**Regla**: El `id` de cada `EmbeddedChunk` se calcula como `f"{course_name}_{section_type.value}"`.

**Aplicación**:
- Permite upsert idempotente — re-procesar el mismo PDF actualiza el chunk existente

---

## BR-04: Parsing determinístico de PDFs

**Regla**: La extracción de secciones de los PDFs se realiza EXCLUSIVAMENTE mediante un script determinístico (sin LLM). No se llama a ningún modelo de lenguaje para extraer el contenido de las secciones.

**Approach**:
1. Extraer texto completo del PDF con `pdfplumber`
2. Normalizar texto (espacios, saltos de línea, caracteres especiales)
3. Detectar headers de sección usando patrones regex que coincidan con las variantes conocidas de cada `SectionType`:

```python
SECTION_PATTERNS: dict[SectionType, list[str]] = {
    SectionType.PRESENTACION:           [r"presentaci[oó]n", r"acerca de"],
    SectionType.SOBRE_ESTE_DIPLOMA:     [r"sobre este diploma", r"sobre el programa"],
    SectionType.COMO_IMPULSAMOS:        [r"c[oó]mo impulsamos", r"impulsamos tu carrera"],
    SectionType.POR_QUE_ESTUDIAR:       [r"por qu[eé] estudiar", r"por qu[eé] este"],
    SectionType.OBJETIVO:               [r"objetivo(s)?", r"metas del programa"],
    SectionType.A_QUIEN_DIRIGIDO:       [r"a qui[eé]n (va )?dirigido", r"dirigido a"],
    SectionType.REQUISITOS:             [r"requisitos", r"prerrequisitos"],
    SectionType.HERRAMIENTAS:           [r"herramientas", r"tecnolog[ií]as"],
    SectionType.MALLA_CURRICULAR:       [r"malla curricular", r"curr[ií]culum", r"contenido"],
    SectionType.PROPUESTA_CAPACITACION: [r"propuesta de capacitaci[oó]n", r"metodolog[ií]a"],
    SectionType.CERTIFICACION:          [r"certificaci[oó]n", r"certificado"],
    SectionType.DOCENTES:               [r"docentes", r"instructores", r"profesores"],
}
```

4. Extraer el texto entre el header detectado y el siguiente header encontrado
5. Si ningún pattern coincide para una sección → `present=False`

**Rationale**: El contenido de los brochures tiene estructura predecible y consistente. Un parser determinístico es más confiable, reproducible y sin costo de LLM para esta tarea.

---

## BR-05: Texto enriquecido para embedding

**Regla**: El texto enviado al generador de embeddings se construye como:

```
f"Programa: {course_name}\nSección: {section_type}\n\n{content}"
```

**Rationale**: Incluir `course_name` y `section_type` mejora la calidad de los embeddings para búsqueda semántica.

---

## BR-06: Manejo de errores por PDF

**Regla**: Un error en el procesamiento de un PDF NO detiene el pipeline. El error se registra en `IngestionReport.errors` y el pipeline continúa con el siguiente PDF.

**Aplicación**:
- Un PDF fallido incrementa `IngestionReport.failed`
- El pipeline solo falla completamente si todos los PDFs fallan

---

## BR-07: Catálogo de brochures conocido

**Regla**: El `course_name` se deriva del nombre del archivo sin extensión. El mapeo a perfiles prioritarios usa este catálogo:

| `course_name` (fragmento del nombre de archivo) | Perfiles prioritarios |
|---|---|
| `power-bi` | analista_datos, bi |
| `diploma-da` / `diploma data analyst` | analista_datos, bi |
| `machine-learning` | data_scientist |
| `diploma-data-scientist` | data_scientist |
| `azure-data-engineering` / `azure DE` | data_engineer |
| `diploma-de` / `diploma data engineer` | data_engineer |
| `n8n-chatbots` / `chatbots-python` / `AIE` | ia_automatizacion |
| `ia-ejecutivos` / `people-analytics` | ejecutivo, no_tecnico |
| `membresia-datapro` / `membresia-ia-developer` | explorador |

---

## BR-08: Límite de keywords

**Regla**: La lista `keywords` de un `EmbeddedChunk` tiene entre 0 y 10 elementos. Si el LLM retorna más de 10, se toman los primeros 10.

---

## BR-09: Reintentos en llamadas al LLM (keywords)

**Regla**: Si la llamada al LLM de keywords falla (timeout, rate limit), el pipeline reintenta hasta 3 veces con backoff exponencial (1s, 2s, 4s). Si falla tras 3 intentos, el chunk se persiste con `keywords=[]` (no se descarta el chunk).

---

## BR-10: Extracción de keywords vía cheap LLM

**Regla**: La generación de keywords se realiza como paso separado DESPUÉS de la extracción determinística, usando un modelo LLM de bajo costo:

- **LOCAL**: Ollama con modelo ligero (e.g. `gemma3:4b`, `llama3.2:3b`)
- **PRODUCCIÓN**: `claude-haiku-4-5` vía Bedrock

**Prompt para keywords**:
```
Dado este texto de un brochure educativo, extrae entre 3 y 5 keywords o frases clave
que representen los temas principales. Responde solo con una lista JSON de strings.

Texto: {content}
```

**Rationale**: Separar la extracción de keywords del parsing determinístico permite usar un modelo barato sin afectar la calidad del contenido principal. El modelo principal (costoso) no se usa para esta tarea.

---

## BR-11: Persistencia de reportes de error

**Regla**: Al finalizar cada ejecución del pipeline, el `IngestionReport` se serializa a JSON y se guarda como archivo.

- **LOCAL**: `{local_reports_dir}/report_{timestamp}.json`
- **PRODUCCIÓN**: S3 key `{s3_reports_prefix}/report_{timestamp}.json`

El nombre de archivo incluye timestamp ISO 8601 con precisión de segundos. No se usa ninguna base de datos para persistir reportes.

---

## BR-12: ENV-based provider selection

**Regla**: El ENV activo se lee del environment variable `INGESTION_ENV` (valores: `local` | `production`). Todos los proveedores (storage, embeddings, keywords LLM) se seleccionan en función del ENV al inicio del pipeline.

| Provider | LOCAL | PRODUCTION |
|---|---|---|
| Storage | Filesystem (`knowledge_source/`) | AWS S3 |
| Embeddings | Ollama (`nomic-embed-text` o equivalente) | Bedrock (`amazon.titan-embed-text-v2:0`) |
| Keywords LLM | Ollama (`gemma3:4b` o equivalente) | Bedrock (`claude-haiku-4-5`) |
| Reports | Filesystem (`reports/`) | S3 (`reports/` prefix) |
