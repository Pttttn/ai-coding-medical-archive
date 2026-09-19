from pathlib import Path

from pypdf import PdfReader, __version__ as pdf_version

from .errors import ServiceError
from .schemas import Page

PARSER_VERSION = f"pypdf-{pdf_version}/text-v1"
SUPPORTED_EXTENSIONS = {".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".pdf"}


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
