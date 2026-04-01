from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib import error, request


logger = logging.getLogger(__name__)


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class OCRSettings:
    enabled: bool
    provider: str
    fallback_only: bool
    min_text_length: int
    render_dpi: int
    api_key: str
    api_url: str
    model: str
    image_detail: str
    timeout_seconds: int


@dataclass
class OCRPageResult:
    text: str
    tables: list[list[list[str]]]


def _load_settings() -> OCRSettings:
    return OCRSettings(
        enabled=_env_flag("OCR_ENABLED", "0"),
        provider=os.getenv("OCR_PROVIDER", "openai").strip().lower() or "openai",
        fallback_only=_env_flag("OCR_FALLBACK_ONLY", "1"),
        min_text_length=max(0, int(os.getenv("OCR_MIN_TEXT_LENGTH", "80"))),
        render_dpi=max(72, int(os.getenv("OCR_RENDER_DPI", "220"))),
        api_key=os.getenv("OCR_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip(),
        api_url=os.getenv("OCR_API_URL", "https://api.openai.com/v1/responses").strip(),
        model=os.getenv("OCR_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        image_detail=os.getenv("OCR_IMAGE_DETAIL", "high").strip() or "high",
        timeout_seconds=max(5, int(os.getenv("OCR_TIMEOUT_SECONDS", "120"))),
    )


@lru_cache(maxsize=1)
def get_ocr_settings() -> OCRSettings:
    return _load_settings()


class OCRBackend:
    def __init__(self, settings: OCRSettings) -> None:
        self.settings = settings
        self._warned_unimplemented = False
        self._page_cache: dict[tuple[str, int], OCRPageResult] = {}

    def extract_page(self, pdf_path: str | Path, page_index: int) -> OCRPageResult:
        cache_key = (str(Path(pdf_path).resolve()), page_index)
        cached = self._page_cache.get(cache_key)
        if cached is not None:
            return cached

        image_bytes = self._render_page_png(pdf_path, page_index, dpi=self.settings.render_dpi)
        result = self._extract_with_provider(image_bytes=image_bytes, pdf_path=Path(pdf_path), page_index=page_index)
        self._page_cache[cache_key] = result
        return result

    def _render_page_png(self, pdf_path: str | Path, page_index: int, dpi: int) -> bytes:
        try:
            import fitz  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "OCR fallback requires the optional 'pymupdf' package. "
                "Install it before enabling OCR."
            ) from exc

        pdf_path = Path(pdf_path)
        with fitz.open(str(pdf_path)) as document:
            page = document.load_page(page_index)
            scale = dpi / 72.0
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            return pixmap.tobytes("png")

    def _extract_with_provider(self, image_bytes: bytes, pdf_path: Path, page_index: int) -> OCRPageResult:
        if self.settings.provider == "openai":
            return self._extract_with_openai(image_bytes=image_bytes, pdf_path=pdf_path, page_index=page_index)
        self._warn_unimplemented(pdf_path, page_index)
        return OCRPageResult(text="", tables=[])

    def _extract_with_openai(self, image_bytes: bytes, pdf_path: Path, page_index: int) -> OCRPageResult:
        if not self.settings.api_key:
            raise RuntimeError(
                "OCR provider 'openai' requires OCR_API_KEY or OPENAI_API_KEY to be set before OCR can run."
            )

        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{image_b64}"
        schema = {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Full page OCR text in natural reading order. Preserve line breaks when useful.",
                },
                "tables": {
                    "type": "array",
                    "description": "Visible tables. Each table is a list of rows, and each row is a list of cell strings.",
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["text", "tables"],
            "additionalProperties": False,
        }
        prompt = (
            "You are an OCR engine for Chinese financial reports. "
            "Read the entire page image carefully. "
            "Return strict JSON with two fields only: "
            "'text' for the full OCR text in natural reading order, and "
            "'tables' for every visible table represented as table -> rows -> cells. "
            "If no table is present, return an empty list for tables. "
            "Do not summarize, do not translate, and do not add commentary."
        )
        payload = {
            "model": self.settings.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": data_url,
                            "detail": self.settings.image_detail,
                        },
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ocr_page_result",
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        response_payload = self._post_json(payload)
        response_text = self._extract_response_text(response_payload)
        if not response_text:
            raise RuntimeError(
                f"OpenAI OCR returned no parseable text for {pdf_path.name} page {page_index + 1}."
            )

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"OpenAI OCR did not return valid JSON for {pdf_path.name} page {page_index + 1}: {response_text[:500]}"
            ) from exc

        text = str(parsed.get("text", "") or "")
        tables = self._normalize_tables(parsed.get("tables", []))
        return OCRPageResult(text=text.strip(), tables=tables)

    def _post_json(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            self.settings.api_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.settings.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - network/runtime diagnostics
            response_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OCR API HTTP {exc.code}: {response_body}") from exc
        except error.URLError as exc:  # pragma: no cover - network/runtime diagnostics
            raise RuntimeError(f"OCR API request failed: {exc}") from exc

    def _extract_response_text(self, payload: object) -> str:
        if isinstance(payload, dict):
            output_text = payload.get("output_text")
            if isinstance(output_text, str) and output_text.strip():
                return output_text.strip()
            if payload.get("type") == "output_text" and isinstance(payload.get("text"), str):
                return str(payload["text"]).strip()
            for value in payload.values():
                extracted = self._extract_response_text(value)
                if extracted:
                    return extracted
            return ""
        if isinstance(payload, list):
            for item in payload:
                extracted = self._extract_response_text(item)
                if extracted:
                    return extracted
        return ""

    def _normalize_tables(self, payload: object) -> list[list[list[str]]]:
        if not isinstance(payload, list):
            return []

        normalized_tables: list[list[list[str]]] = []
        for table in payload:
            if not isinstance(table, list):
                continue
            normalized_rows: list[list[str]] = []
            for row in table:
                if not isinstance(row, list):
                    continue
                normalized_rows.append([str(cell) if cell is not None else "" for cell in row])
            if normalized_rows:
                normalized_tables.append(normalized_rows)
        return normalized_tables

    def _warn_unimplemented(self, pdf_path: Path, page_index: int) -> None:
        if self._warned_unimplemented:
            return
        logger.warning(
            "OCR is enabled for %s page %s, but the OCR provider '%s' is still a skeleton. "
            "Implement OCRBackend._call_ocr_text/_call_ocr_tables to return actual results.",
            pdf_path.name,
            page_index + 1,
            self.settings.provider,
        )
        self._warned_unimplemented = True


@lru_cache(maxsize=1)
def get_ocr_backend() -> OCRBackend | None:
    settings = get_ocr_settings()
    if not settings.enabled:
        return None
    return OCRBackend(settings)
