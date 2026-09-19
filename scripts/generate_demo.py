"""Deterministic, wholly synthetic fixtures. Never ingests real patient records."""
from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed"
CORPUS = ROOT / "sample_docs"
TAGS = ["анализы", "кардиология", "наблюдение", "липиды", "давление", "сон", "активность", "питание", "терапевт", "дневник", "контроль", "рекомендации", "транскрипт", "лаборатория", "самочувствие", "синтетика", "осмотр", "вопросы"]

FACTS = [
    ("visit-01.md", "Cedar visit", "The Cedar visit reference code is SYN-CASE-7F29.", "What is the reference code of the Cedar visit?", "SYN-CASE-7F29"),
    ("visit-02.md", "Amber follow-up", "The Amber follow-up interval is 11 weeks.", "How many weeks until the Amber follow-up?", "11"),
    ("visit-03.md", "Saffron notebook", "The Saffron notebook contains 37 evening observations.", "How many evening observations are in the Saffron notebook?", "37"),
    ("visit-04.md", "Juniper laboratory", "The Juniper laboratory sample was collected on 2024-02-17.", "On what date was the Juniper laboratory sample collected?", "2024-02-17"),
    ("visit-05.md", "Willow walking diary", "The Willow walking diary records a route of 1730 metres.", "How long is the route recorded in the Willow walking diary?", "1730"),
    ("visit-06.md", "Birch appointment", "The Birch appointment took place in room B-217.", "In which room did the Birch appointment take place?", "B-217"),
    ("visit-07.md", "Orchid measurement", "The Orchid synthetic measurement result is 4.73 mmol/L.", "What is the Orchid synthetic measurement result in mmol/L?", "4.73"),
    ("visit-08.md", "Maple instructions", "The Maple instructions specify a violet notebook with a triangle on its cover.", "What colour notebook is specified in the Maple instructions?", "violet"),
    ("visit-09.md", "Pine review", "The Pine review was scheduled for 2025-09-23.", "What date was scheduled for the Pine review?", "2025-09-23"),
    ("visit-10.md", "Hazel transcript", "The Hazel transcript contains exactly 9 prepared questions.", "How many prepared questions does the Hazel transcript contain?", "9"),
    ("visit-11.md", "Rowan diary", "The Rowan diary records no dizziness on 2025-01-14.", "Was dizziness reported in the Rowan diary on 2025-01-14?", "no dizziness"),
    ("visit-12.md", "Elm prescription", "The Elm prescription says 2.5 mg once daily, but actual intake is unknown.", "What dose does the Elm prescription state and is actual intake confirmed?", "2.5"),
]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pdf(path: Path, number: int, day: str, value: float) -> str:
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#145b60")
    title = f"Synthetic laboratory report {number:02d}"
    quote = f"LDL cholesterol {value:.2f} mmol/L"
    story = [Paragraph("LOCAL MEDICAL ARCHIVE", styles["Title"]),
             Paragraph("SYNTHETIC DEMO - NOT A REAL PATIENT", styles["Heading2"]),
             Spacer(1, 16), Paragraph(title, styles["Heading1"]),
             Paragraph(f"Document date: {day}<br/>Patient: Alex Example<br/>Clinic: Fictional Cedar Clinic", styles["Normal"]),
             Spacer(1, 20)]
    table = Table([["Test", "Result", "Unit"], ["LDL cholesterol", f"{value:.2f}", "mmol/L"], ["Glucose", f"{4.60 + number * .03:.2f}", "mmol/L"]], colWidths=[250, 90, 90])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dff0ed")), ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#b9cfcd")), ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
    story += [table, Spacer(1, 18), Paragraph(quote, styles["Normal"]), Spacer(1, 10), Paragraph("The values are generated fixtures for software testing. They do not establish a diagnosis. A recommendation or prescription is not evidence of medication intake. No medical advice is provided.", styles["Normal"])]
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=48).build(story)
    from pypdf import PdfReader
    return PdfReader(path).pages[0].extract_text()


def generate_seed() -> None:
    (SEED / "originals").mkdir(parents=True, exist_ok=True)
    records = []
    for i in range(36):
        day = (date(2024, 1, 12) + timedelta(days=i * 20)).isoformat()
        value = round(3.1 + (i % 9) * .17, 2)
        is_pdf = i < 6
        transcript = not is_pdf and i % 2 == 0
        dtype = "LAB_REPORT" if is_pdf else "VISIT_TRANSCRIPT" if transcript else "NOTE"
        title = f"Липидный профиль · {day}" if is_pdf else f"Приём терапевта · {day}" if transcript else f"Дневник самочувствия · {day}"
        quote = f"LDL cholesterol {value:.2f} mmol/L"
        text = f"СИНТЕТИЧЕСКИЙ ПРИМЕР. Вымышленный пациент, не медицинский совет.\nДата: {day}.\n" + (f"Пациент: Алексей Примеров. Врач: Ирина Тестовая. Клиника: Учебная клиника.\nВрач: расскажите о дневнике наблюдений.\nПациент: зафиксировано {i + 2} записей. Головокружение отрицаю.\nРекомендация: обсудить записи на следующем визите; фактический приём препаратов неизвестен.\n" if transcript else f"Личная заметка: прогулка {18 + i} минут, сон {6 + (i % 3)} часов. Головокружения не отмечал.\nДля следующего визита подготовлено {2 + i % 5} вопросов.\n")
        if is_pdf:
            text = pdf(SEED / "originals" / f"lab-{i+1:02d}.pdf", i + 1, day, value)
        else:
            quote = "Головокружение отрицаю." if transcript else "Головокружения не отмечал."
            write(SEED / "originals" / f"record-{i+1:02d}.txt", text)
        fact = {"type": "LAB_RESULT" if is_pdf else "SYMPTOM", "name": "LDL cholesterol" if is_pdf else "Головокружение", "valueNumber": value if is_pdf else None, "valueText": None if is_pdf else "Отрицается в источнике", "unit": "mmol/L" if is_pdf else None, "eventDate": day, "assertionStatus": "CONFIRMED" if is_pdf else "NEGATED", "confidence": None, "provenance": {"page": 1 if is_pdf else None, "sourceText": quote}}
        if i < 5:
            fact["correction"] = {"valueNumber": round(value + .01, 2), "valueText": "Учебная ручная поправка: исходное значение сохранено в цитате", "unit": "mmol/L"}
        records.append({"id": str(uuid5(NAMESPACE_URL, f"local-medical-archive/synthetic/{i}")), "title": title, "documentType": dtype, "documentDate": day, "sourceType": "PDF" if is_pdf else "TEXT", "originalFile": f"originals/lab-{i+1:02d}.pdf" if is_pdf else f"originals/record-{i+1:02d}.txt", "text": text, "pages": [{"pageNumber": 1, "text": text}], "tags": sorted(set(["синтетика", TAGS[i % len(TAGS)], TAGS[(i + 4) % len(TAGS)], "анализы" if is_pdf else "транскрипт" if transcript else "дневник"])), "summary": "Заранее подготовленная синтетическая запись для демонстрации архива. Не результат нового AI inference.", "facts": [fact]})
    write(SEED / "records.json", json.dumps(records, ensure_ascii=False, indent=2))
    write(SEED / "README.md", "# Происхождение seed\n\n36 детерминированных синтетических записей одного вымышленного пациента за 2024–2025 годы; 6 PDF с текстовым слоем, 15 транскриптов и 15 заметок. В первых пяти лабораторных фактах сохранена учебная пользовательская поправка +0.01 с неизменённой исходной цитатой. Генератор scripts/generate_demo.py. Извлечения маркированы synthetic-seed, это не измерение качества LLM. Ни один документ не является медицинской рекомендацией.\n")


def generate_corpus() -> None:
    questions = []
    for filename, title, fact, question, answer in FACTS:
        source = f"visits/{filename}"
        write(CORPUS / source, f"# {title}\n\nSYNTHETIC MEDICAL ARCHIVE. Fictional patient; software test data, not medical guidance.\n\n## Recorded observation\n{fact}\n\n## Source scope\nThis record reports only the named encounter. It does not establish a diagnosis or confirm medication use. Technical upload time is not the date of an encounter. Unstated information is unknown.\n")
        questions.append({"id": f"fact-{len(questions)+1:02d}", "category": "exact_fact", "question": question, "expected": answer, "expectedSources": [source], "allowAbstain": False})
    write(CORPUS / "overview.md", "# Archive guide\n\nThis is a synthetic medical archive for retrieval testing. It contains fictional visits, laboratory observations, prescriptions with unknown intake, a two-year daily wellness diary, and software metadata examples. All records concern a fictional participant Alex Example. Monthly diaries cover January 2024 through December 2025. They record self-reported sleep, walking, observation counts, energy and the status of notes. Entries are not diagnoses. A missing measurement is unknown, and an explicit denial must stay negative. The Cedar and Amber encounters are separate; their facts must not be merged. Code files describe synthetic schema constants and are indexed as text, never executed.\n")
    feelings = ["rested after an early night", "tired after a late evening", "comfortable during a short walk", "busy with household tasks", "calm after a quiet afternoon", "more energetic after resting", "distracted by a changing schedule"]
    activities = ["walked around the indoor courtyard", "completed a quiet reading session", "visited the fictional botanical garden", "sorted the previous week's paper notes", "prepared questions for the next appointment", "walked beside the fictional canal", "reviewed the observation notebook"]
    uncertainties = ["No blood pressure measurement was taken", "No medication intake was recorded", "The exact time of the walk was not recorded", "No glucose measurement was taken", "The source of the pedometer estimate is self-report", "The pulse measurement was omitted", "No temperature measurement was available"]
    for year in (2024, 2025):
        for month in range(1, 13):
            blocks = [f"# Synthetic wellness diary {year}-{month:02d}\n\nFictional longitudinal source, generated for retrieval tests. This is not medical advice. Dates below are observation dates, not upload timestamps.\n"]
            for d in range(1, calendar.monthrange(year, month)[1] + 1):
                dt = date(year, month, d)
                n = (dt - date(2024, 1, 1)).days
                minutes = 12 + (n * 17) % 53
                sleep = 5.5 + ((n * 7) % 13) / 4
                energy = 2 + (n * 3) % 7
                blocks.append(f"## {dt.isoformat()} — entry DAY-{n+1:04d}\nOn this observation date the fictional participant {activities[n % 7]} and described feeling {feelings[(n // 3) % 7]}. The recorded walk lasted {minutes} minutes. Estimated sleep was {sleep:.2f} hours, and the self-reported energy score was {energy} out of 10. The notebook contains {1 + n % 4} observations for this day, with {n % 3} questions left for a future discussion.\n{uncertainties[(n // 5) % 7]}; this missing value must remain unknown. The participant explicitly denied dizziness during this observation. No new diagnosis was established in the diary. This entry records what was written and does not infer causation from sleep, walking or energy. Planned actions and actual actions are separate: the notebook mentions a plan to review the previous {3 + n % 8} days, but completion of that review is not documented. The daily source label is OBS-{year}-{month:02d}-{d:02d}.\n")
            write(CORPUS / "diary" / f"{year}-{month:02d}.md", "\n".join(blocks))
    extras = {
        "schemas/catalog.json": json.dumps({"synthetic": True, "formatVersion": "LMA-DEMO-1", "datePolicy": "unknown is null", "sourceStatuses": ["CONFIRMED", "SUSPECTED", "NEGATED", "PRESCRIBED", "UNKNOWN"], "reviewStatuses": ["UNREVIEWED", "CONFIRMED", "CORRECTED", "REJECTED"]}, indent=2),
        "schemas/index.yaml": "synthetic: true\narchive_code: LMA-COPPER-608\nretention: local_snapshot\nunknown_date: null\nsource_policy: immutable_revision\n",
        "schemas/reference.py": '# Synthetic schema sample, indexed as data only.\nSYNTHETIC_LABEL = "LMA-DEMO-1"\nMAX_CORRECTIVE_RETRIES = 2\nREVIEW_STATES = ("UNREVIEWED", "CONFIRMED", "CORRECTED", "REJECTED")\n',
        "schemas/reference.js": '// Synthetic schema sample, never executed by the indexer.\nexport const archivePolicy = {unknownDate: null, automaticExternalSending: false};\n',
        "schemas/reference.ts": '// Synthetic schema sample, indexed only as text.\nexport type AssertionStatus = "CONFIRMED" | "SUSPECTED" | "NEGATED" | "PRESCRIBED" | "UNKNOWN";\n',
        "notes/source-policy.txt": "Synthetic source policy: a prescription is not evidence of intake. User correction does not replace the original source quotation. An undated medical observation must not receive the technical upload date. Document identifiers are removed from a consultation export.\n",
        "visits/conflict-a.md": "# Synthetic Spruce original note\nThe Spruce observation initially records 17 minutes of walking on 2025-04-03. This is the original source value.\n",
        "visits/conflict-b.md": "# Synthetic Spruce corrected note\nA later user correction changes the Spruce walking duration on 2025-04-03 to 19 minutes. The original source had 17 minutes. This is a user correction, not a new source quotation.\n",
    }
    for path, value in extras.items():
        write(CORPUS / path, value)
    questions.extend([
        {"id": "paraphrase-01", "category": "paraphrase", "question": "What identifier lets me look up the Cedar encounter?", "expected": "SYN-CASE-7F29", "expectedSources": ["visits/visit-01.md"], "allowAbstain": False},
        {"id": "paraphrase-02", "category": "paraphrase", "question": "How long is the waiting period before returning for Amber?", "expected": "11", "expectedSources": ["visits/visit-02.md"], "allowAbstain": False},
        {"id": "overview-01", "category": "overview", "question": "What kinds of records are in this synthetic archive?", "expected": "diary", "expectedSources": ["overview.md"], "allowAbstain": False},
        {"id": "multi-01", "category": "multiple_sources", "question": "Give the Cedar reference code and the Amber follow-up interval.", "expected": "SYN-CASE-7F29", "expectedSources": ["visits/visit-01.md", "visits/visit-02.md"], "allowAbstain": False},
        {"id": "negation-01", "category": "negation", "question": "Does the Elm prescription prove the medication was taken?", "expected": "unknown", "expectedSources": ["visits/visit-12.md"], "allowAbstain": False},
        {"id": "conflict-01", "category": "contradiction", "question": "What were the original and corrected Spruce walking durations?", "expected": "19", "expectedSources": ["visits/conflict-a.md", "visits/conflict-b.md"], "allowAbstain": False},
        {"id": "missing-01", "category": "missing", "question": "What is the fictional participant's blood group?", "expected": None, "expectedSources": [], "allowAbstain": True},
        {"id": "unrelated-01", "category": "unrelated", "question": "What is the capital of Argentina?", "expected": None, "expectedSources": [], "allowAbstain": True},
        {"id": "russian-01", "category": "paraphrase", "question": "Какой код указан у визита Cedar?", "expected": "SYN-CASE-7F29", "expectedSources": ["visits/visit-01.md"], "allowAbstain": False},
    ])
    write(ROOT / "evaluation" / "questions.json", json.dumps(questions, ensure_ascii=False, indent=2))
    paths = sorted(p for p in CORPUS.rglob("*") if p.is_file())
    entries = [{"path": p.relative_to(CORPUS).as_posix(), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    size = sum(x["bytes"] for x in entries)
    assert size >= 512000, size
    assert len({x["sha256"] for x in entries}) == len(entries)
    write(ROOT / "evaluation" / "corpus-manifest.json", json.dumps({"provenance": "Deterministically authored synthetic data, no real patients, no third-party sources", "indexedBytes": size, "files": entries}, indent=2))
    print(f"Generated {len(entries)} unique corpus files, {size} bytes, {len(questions)} questions, 36 seed records")


if __name__ == "__main__":
    generate_seed()
    generate_corpus()
