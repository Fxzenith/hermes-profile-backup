---
name: markitdown
description: Use when converting files to Markdown for LLM ingestion.
---

# MarkItDown — file → Markdown conversion

Microsoft's MarkItDown: lightweight Python utility converting documents to Markdown for LLM/text-analysis pipelines. Installed venv: `/root/.venvs/markitdown` (`markitdown[all]`). Repo clone: `/root/markitdown` (upstream https://github.com/microsoft/markitdown, live branch — check `git -C /root/markitdown pull` if behavior looks stale). Source config truth: `/root/markitdown/packages/markitdown/src/markitdown/converters/`.

## Quick start

```bash
# CLI (binary lives in the venv — run it directly or activate)
/root/.venvs/markitdown/bin/markitdown file.pdf > file.md
/root/.venvs/markitdown/bin/markitdown file.docx -o file.md
cat file.html | /root/.venvs/markitdown/bin/markitdown   # stdin pipe

# any extras missing (e.g. only pdf+docx+pptx)
/root/.venvs/markitdown/bin/pip install 'markitdown[pdf, docx, pptx]'
```

## Python API

```python
from markitdown import MarkItDown
md = MarkItDown()                    # enable_plugins=False default
result = md.convert("test.xlsx")     # path, URL, or file-like
print(result.text_content)

# LLM vision captions for images/pptx slides (needs an OpenAI-compatible client)
from openai import OpenAI
md = MarkItDown(llm_client=OpenAI(), llm_model="gpt-4o", llm_prompt="optional")
```

Use `md.convert_stream(...)` / `md.convert_local(...)` for file-like inputs in hostile environments (see Pitfalls).

## Supported formats (v0.1.x, this clone)

PDF, PPTX, DOCX, XLSX/XLS, images (EXIF + OCR), audio (EXIF + transcription), HTML, plain text (CSV/JSON/XML), ZIP (recurses contents), Outlook .msg, EPUB, YouTube URLs (transcript), RSS, Wikipedia, Bing SERP. Converter modules in `converters/_<fmt>_converter.py` — grep there for exact behavior/limitations of a format before promising output shape.

## Extras / advanced

- `[all]` installs every optional dep: pptx, docx (mammoth), xlsx (pandas/openpyxl), xls, pdf (pdfminer.six, pdfplumber), outlook, az-doc-intel, az-content-understanding, audio-transcription (pydub + SpeechRecognition), youtube-transcription.
- Azure Document Intelligence (better PDFs/scans): `markitdown file.pdf -o out.md -d -e "<endpoint>"`; in Python `MarkItDown(docintel_endpoint="...")`.
- Plugins disabled by default: `markitdown --list-plugins`, `--use-plugins file.pdf`. Community plugins via GitHub `#markitdown-plugin` (e.g. `markitdown-ocr` adds LLM-vision OCR of embedded images).
- Docker: `docker run --rm -i markitdown:latest < file.pdf > out.md`.

## Pitfalls

- Every run prints `[W:onnxruntime ... Failed to detect devices under "/sys/class/drm/card0"]` on GPU-less VPSes — harmless, ignore (markitdown 0.1.7+ uses onnxruntime for file-type detection).
- Base `pip install markitdown` has NO format converters beyond HTML/plain text — always use `[all]` or explicit extras.
- Python here is PEP 668 externally-managed — always use a venv (never system pip).
- Result object: `.text_content` holds the markdown (also `.metadata` / `.title`).
- Untrusted input: the converter opens files/URLs with the process's privileges; sanitize inputs and use `convert_stream()`/`convert_local()`.

## Verify

```bash
/root/.venvs/markitdown/bin/markitdown --version
echo '# hi' > /tmp/x.html && /root/.venvs/markitdown/bin/markitdown /tmp/x.html
```