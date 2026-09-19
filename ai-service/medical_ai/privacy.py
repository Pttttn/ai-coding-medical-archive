import re
from typing import Any

from .errors import ServiceError

PRIVACY_SCHEMA = {"type": "object", "properties": {
    "identifiers": {"type": "array", "items": {"type": "object", "properties": {
        "text": {"type": "string"}, "category": {"type": "string", "enum":
        ["PERSON", "DOCTOR", "CLINIC", "ADDRESS", "DOB", "CONTACT", "IDENTIFIER"]}},
        "required": ["text", "category"]}},
    "warnings": {"type": "array", "items": {"type": "string"}}}, "required": ["identifiers", "warnings"]}


def redact_known_people(text: str) -> str:
    """Propagate labelled names across the entire package without crossing line boundaries."""
    label_pattern = (
        r"\b(?P<label>(?i:ФИО|пациент|patient(?:[ \t]+name)?|врач|doctor))[ \t]*[:=][ \t]*"
        r"(?P<name>[А-ЯA-ZЁ][а-яa-zё]+(?:[ \t]+[А-ЯA-ZЁ][а-яa-zё]+){1,2})"
    )
    aliases = {}
    for match in re.finditer(label_pattern, text):
        name = " ".join(match["name"].split())
        parts = name.split()
        variants = {name}
        # Russian labels commonly use surname-first; a question often uses given-name-first.
        if len(parts) >= 2:
            pair = [parts[0], parts[1]] if re.search(r"[А-Яа-яЁё]", name) else [parts[0], parts[-1]]
            variants.update((" ".join(pair), " ".join(reversed(pair))))
        existing = next((aliases[value.casefold()] for value in variants if value.casefold() in aliases), None)
        if existing is None:
            kind = "DOCTOR" if match["label"].casefold() in {"врач", "doctor"} else "PERSON"
            # Letter suffixes do not masquerade as medical quantities in invariants.
            index, suffix = len(set(aliases.values())), ""
            while True:
                suffix = chr(ord("A") + index % 26) + suffix
                index = index // 26 - 1
                if index < 0:
                    break
            existing = f"[{kind}_{suffix}]"
        for value in variants:
            aliases.setdefault(value.casefold(), existing)
    for name in sorted(aliases, key=len, reverse=True):
        text = re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)", lambda _: aliases[name], text, flags=re.I)
    return text


def deterministic_sanitize(text: str) -> str:
    text = redact_known_people(text)
    patterns = [
        (r"(?i)\b[\w.+-]+@[\w.-]+\.[a-zа-я]{2,}\b", "[EMAIL]"),
        (r"(?<!\w)(?:\+7|\+1|8)\s*[(-]?\d{3}[)\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)", "[PHONE]"),
        (r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "[INTERNAL_REF]"),
        (r"(?i)(?:[A-Z]:[\\/]|/(?:data|home|Users|uploads|app)/)[^\s\n<>]+", "[LOCAL_PATH]"),
        (r"(?i)\b[^\s/\\]+\.(?:pdf|docx?|txt|md|csv|json|yaml)\b", "[SOURCE_FILE]"),
        (r"(?im)\b(?:дата рождения|date of birth|DOB|родился|родилась)\s*[:=]?\s*\d{1,4}[./-]\d{1,2}[./-]\d{1,4}", "[DOB]"),
        (r"(?im)\b(?:СНИЛС|ОМС|полис|паспорт|patient\s*id|insurance\s*id|номер документа|document\s*id)\s*[:=#№]?\s*[\w-]+(?:[ -]\d+)*", "[IDENTIFIER]"),
        (r"(?im)\b(?:адрес|address|клиника|clinic|hospital)\s*[:=]\s*[^\n;.]+", "[LOCATION]"),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text


def clinical_signature(text: str) -> tuple[list[str], list[str]]:
    # Identifiers have already been removed. Remaining numbers and explicit negations are immutable.
    return (re.findall(r"\d+(?:[.,]\d+)?", text),
            re.findall(r"(?i)\b(?:не|нет|без|отрицает|отрицательный|no|not|without|denies|negative)\b", text))


def consultation(provider: Any, question: str, contexts: list[str]) -> dict:
    warnings = ["Требуется ручная проверка перед экспортом. Полная анонимность не гарантируется.",
                "Медицинские даты, редкие диагнозы, процедуры и точный возраст могут быть косвенными идентификаторами."]
    selected, size = [], 0
    for text in contexts:
        if size + len(text) > 28000:
            warnings.append("Контекст ограничен 28000 символами. Проверьте полноту выбранных данных.")
            break
        selected.append(text)
        size += len(text)
    content = "# Контекст для консультации\n\n## Вопрос\n\n" + question + "\n\n## Данные архива\n\n" + "\n\n---\n\n".join(selected)
    number_pattern = r"\d+(?:[.,]\d+)?\s*(?:мг|мкг|мл|ммоль/л|mg|mcg|ml|mmol/L|mmHg)\b"
    medical_numbers = re.findall(number_pattern, content, re.I)
    original_negations = clinical_signature(content)[1]
    content = deterministic_sanitize(content)
    if (medical_numbers != re.findall(number_pattern, content, re.I)
            or original_negations != clinical_signature(content)[1]):
        raise ServiceError("CLINICAL_CONTENT_CHANGED", "Очистка затронула медицинские данные; уточните текст.", 502)
    before = clinical_signature(content)
    output = provider.json("TASK: privacy_pass. Inspect the ENTIRE package including the question and headings. "
        "List EXACT substrings containing personal names, doctor names, clinic names, addresses, birth dates, "
        "contacts or identifiers that must be redacted. Do not redact medical measurements, dates of medical "
        "events, doses, ages, codes for clinical procedures, negations, or already bracketed placeholders. "
        "Do not rewrite the text. Return identifiers:[{text,category}], warnings:[string] about quasi-identifiers. "
        "Never include the actual personal data in warnings.", {"package": content}, PRIVACY_SCHEMA)
    identifiers = output.get("identifiers")
    if not isinstance(identifiers, list):
        raise ServiceError("PRIVACY_CHECK_FAILED", "Локальная проверка приватности вернула неверный результат.", 502)
    replacements = {}
    for item in identifiers:
        span, category = item.get("text", ""), item.get("category", "IDENTIFIER")
        if not span or span not in content or span.startswith("["):
            continue
        if clinical_signature(span) != ([], []):
            # Ambiguous numeric/negated span needs manual handling; never silently alter a dose or date.
            warnings.append("Обнаружен возможный идентификатор с числами/отрицанием: требуется ручное удаление.")
            continue
        replacements.setdefault(span, f"[{category}_{len(replacements) + 1}]")
    for span in sorted(replacements, key=len, reverse=True):
        content = content.replace(span, replacements[span])
    content = deterministic_sanitize(content)
    # Strip the numeric suffixes in generated pseudonyms before checking clinical invariants.
    comparable = re.sub(r"\[(PERSON|DOCTOR|CLINIC|ADDRESS|DOB|CONTACT|IDENTIFIER)_\d+\]", r"[\1]", content)
    if clinical_signature(comparable) != before:
        raise ServiceError("CLINICAL_CONTENT_CHANGED", "Проверка обнаружила изменение медицинских чисел или отрицаний.", 502)
    # Never forward model-generated warning text: it could echo private identifiers.
    if output.get("warnings"):
        warnings.append("Локальная модель отметила дополнительные косвенные идентификаторы; проверьте весь пакет.")
    return {"content": content, "warnings": list(dict.fromkeys(warnings))}
