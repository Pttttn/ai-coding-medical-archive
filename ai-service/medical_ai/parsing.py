from pathlib import Path
import re

import pdfplumber
from pypdf import PdfReader, __version__ as pdf_version

from .errors import ServiceError
from .schemas import Page

PARSER_VERSION = f"pypdf-{pdf_version}/text-v1"
LAB_TABLE_PARSER_VERSION = f"{PARSER_VERSION}+pdfplumber-table-v1"
SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def confined_path(path: str | Path, root: Path) -> Path:
    root = root.resolve()
    candidate = Path(path).resolve()
    if not candidate.is_relative_to(root):
        raise ServiceError("PATH_NOT_ALLOWED", "Путь вне разрешённого каталога.", 403)
    return candidate


def parse_file(path: Path, max_bytes: int) -> tuple[str, list[Page], list[str]]:
    if path.stat().st_size > max_bytes:
        raise ServiceError("FILE_TOO_LARGE", "Файл превышает ограничение размера.")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ServiceError("UNSUPPORTED_FORMAT", "Формат файла не поддерживается.")
    if path.suffix.lower() != ".pdf":
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            raise ServiceError("INVALID_ENCODING", "Ожидается текст в кодировке UTF-8.") from exc
        return text, [Page(text=text)], []
    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            raise ServiceError("ENCRYPTED_PDF", "Зашифрованный PDF не поддерживается.")
        pages = [Page(pageNumber=i + 1, text=page.extract_text() or "") for i, page in enumerate(reader.pages)]
    except ServiceError:
        raise
    except Exception as exc:
        raise ServiceError("MALFORMED_PDF", "Не удалось прочитать PDF.") from exc
    if not any(page.text.strip() for page in pages):
        raise ServiceError("UNSUPPORTED_OCR_REQUIRED", "PDF не содержит текстового слоя; требуется OCR.")
    missing = [str(p.pageNumber) for p in pages if not p.text.strip()]
    warnings = ["Текст извлечён не со всех страниц PDF. Пустые страницы: " + ", ".join(missing)] if missing else []
    return "\n\n".join(p.text for p in pages), pages, warnings


def parse_pdf_lab_tables(path: Path) -> tuple[str, list[Page]] | None:
    """Reflow four-column laboratory tables while preserving surrounding PDF text.

    This parser is opt-in. Spans reference this versioned text extraction;
    the uploaded PDF remains the immutable original for visual verification.
    """
    def clean(value: str | None) -> str:
        return " ".join((value or "").split())

    def is_lab_header(row: list[str | None]) -> bool:
        if len(row) != 4:
            return False
        cells = [clean(cell).casefold() for cell in row]
        return (cells[0] in {"тест", "показатель", "test"}
                and cells[1] in {"результат", "result"}
                and cells[2] in {"ед. измерения", "ед.измерения", "единица", "единицы", "unit"}
                and cells[3] in {"референсный интервал", "референс", "reference"})

    try:
        with pdfplumber.open(path) as pdf:
            # An embedded table in a visit is not sufficient to classify the document.
            first_page_text = pdf.pages[0].extract_text() if pdf.pages else ""
            if not re.search(r"(?:дата (?:взятия материала|выдачи результата)|specimen date|result date)\s*:",
                             first_page_text or "", re.I):
                return None
            pages: list[Page] = []
            found = False
            for number, page in enumerate(pdf.pages, 1):
                tables = [(table, table.extract()) for table in page.find_tables()]
                tables = [(table, rows) for table, rows in tables if rows and is_lab_header(rows[0])]
                if not tables:
                    pages.append(Page(pageNumber=number, text=page.extract_text() or ""))
                    continue
                found = True
                segments = ["Лабораторные исследования"] if number == 1 else []
                left, cursor, right, page_bottom = page.bbox

                def band(top: float, bottom: float, table_bbox=None) -> None:
                    # Zero-height bands occur for tables flush with a page edge or another table.
                    if bottom <= top:
                        return
                    region = page.crop((left, top, right, bottom))
                    if table_bbox is not None:
                        # Keep text printed beside a table (comments, stamps) instead of dropping it.
                        region = region.outside_bbox(table_bbox)
                    text = region.extract_text() or ""
                    if text.strip():
                        segments.append(text)

                for table, rows in sorted(tables, key=lambda item: item[0].bbox[1]):
                    top, bottom = table.bbox[1], table.bbox[3]
                    if top < cursor:
                        raise ValueError("Overlapping laboratory tables")
                    band(cursor, top)
                    segments.append("Показатель\tРезультат\tЕдиница\tРеференс")
                    segments.extend("\t".join(clean(cell) for cell in row) for row in rows[1:])
                    segments.append("")  # End this table before surrounding report text.
                    band(top, bottom, table.bbox)
                    cursor = bottom
                band(cursor, page_bottom)
                pages.append(Page(pageNumber=number, text="\n".join(segments)))
    except Exception as exc:
        raise ServiceError("LAB_TABLE_PARSE_FAILED", "Не удалось разобрать лабораторную таблицу PDF.") from exc
    if not found:
        return None
    if pages and not pages[0].text.startswith("Лабораторные исследования\n"):
        pages[0].text = "Лабораторные исследования\n" + pages[0].text
    return "\n\n".join(p.text for p in pages), pages
