"""Synthetic-only geometry regression for laboratory PDF tables."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from medical_ai.main import create_app

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from medical_ai.laboratory import annotate_laboratory, project_laboratory
from medical_ai.parsing import LAB_TABLE_PARSER_VERSION, parse_pdf_lab_tables
from medical_ai.source_ir import SourceIR, build_source_ir, resolve_span


def synthetic_report(path: Path):
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(str(path), pagesize=A4)
    header = ["Test", "Result", "Unit", "Reference"]
    long_reference = Paragraph("deficient &lt;20; borderline 20-29; sufficient &gt;=30", styles["Normal"])
    first = Table([header, ["LDL", "4.1", "mmol/L", "<3.0"],
                   ["Vitamin D", "18.5", "ng/mL", long_reference]], colWidths=[130, 80, 75, 200])
    second = Table([header, ["Creatinine", "92", "umol/L", "62-106"]], colWidths=[130, 80, 75, 200])
    for table in (first, second):
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    document.build([Paragraph("Specimen date: 2026-05-13 08:30:00", styles["Normal"]),
                    Paragraph("Result date: 2026-05-14 09:00:00", styles["Normal"]),
                    Spacer(1, 12), first, PageBreak(), second])


def test_geometry_preserves_rows_dates_multiline_reference_and_pages(tmp_path):
    path = tmp_path / "synthetic.pdf"
    synthetic_report(path)
    parsed = parse_pdf_lab_tables(path)
    assert parsed is not None
    _, pages = parsed
    ir = SourceIR.model_validate(build_source_ir("synthetic", pages, LAB_TABLE_PARSER_VERSION))
    lab = annotate_laboratory(ir)
    assert lab is not None and len(lab.rows) == lab.candidateRows == 3
    assert {d.role for d in lab.dates} == {"RESULT", "SPECIMEN"}
    assert [row.name for row in lab.rows] == ["LDL", "Vitamin D", "Creatinine"]
    assert [row.result.numericValue for row in lab.rows] == ["4.1", "18.5", "92"]
    assert lab.rows[1].referenceRaw == "deficient <20; borderline 20-29; sufficient >=30"
    assert [pages[row.source.pageIndex].pageNumber for row in lab.rows] == [1, 1, 2]
    assert all(resolve_span(ir.pages, row.source) == row.sourceText for row in lab.rows)
    extracted, _ = project_laboratory(ir, lab)
    assert extracted.documentDate.isoformat() == "2026-05-14"
    assert [fact.provenance.page for fact in extracted.facts] == [1, 1, 2]


def test_unrelated_pdf_does_not_become_laboratory(tmp_path):
    path = tmp_path / "note.pdf"
    SimpleDocTemplate(str(path)).build([Paragraph("A visit note without a lab table.", getSampleStyleSheet()["Normal"])])
    assert parse_pdf_lab_tables(path) is None


@pytest.mark.parametrize("profile", ["lab-rows-v1", "clinical-v1", "clinical-reviewed-v1"])
def test_internal_process_uses_versioned_table_parser_without_model(services, profile):
    services.settings.extraction_profile = profile
    services.settings.upload_dir.mkdir()
    path = services.settings.upload_dir / "synthetic.pdf"
    synthetic_report(path)
    with TestClient(create_app(services)) as client:
        response = client.post("/internal/process", headers={"X-Internal-Token": "test-secret"},
                               json={"documentId": "synthetic", "version": 1, "title": "Synthetic lab",
                                     "filePath": str(path)})
    assert response.status_code == 200
    result = response.json()
    assert result["parserVersion"] == LAB_TABLE_PARSER_VERSION
    assert result["sourceIR"]["parserVersion"] == LAB_TABLE_PARSER_VERSION
    assert result["laboratory"]["candidateRows"] == 3
    assert len(result["extraction"]["facts"]) == 3
    assert result["model"] == "deterministic:lab-rows-v1"
    assert not services.provider.calls


def test_table_on_second_page_keeps_source_page_number(tmp_path):
    path = tmp_path / "second-page.pdf"
    styles = getSampleStyleSheet()
    table = Table([["Test", "Result", "Unit", "Reference"],
                   ["Glucose", "5.8", "mmol/L", "3.9-6.1"]], colWidths=[130, 80, 75, 200])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(str(path)).build([
        Paragraph("Result date: 2026-05-14", styles["Normal"]),
        PageBreak(), table])
    _, pages = parse_pdf_lab_tables(path)
    ir = SourceIR.model_validate(build_source_ir("synthetic", pages, LAB_TABLE_PARSER_VERSION))
    lab = annotate_laboratory(ir)
    assert lab is not None and len(lab.rows) == 1
    assert lab.rows[0].source.pageIndex == 1
    assert project_laboratory(ir, lab)[0].facts[0].provenance.page == 2


def test_visit_with_embedded_lab_table_is_not_reclassified(tmp_path):
    path = tmp_path / "visit.pdf"
    styles = getSampleStyleSheet()
    table = Table([["Test", "Result", "Unit", "Reference"],
                   ["Glucose", "5.8", "mmol/L", "3.9-6.1"]], colWidths=[130, 80, 75, 200])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(str(path)).build([Paragraph("Visit note, 2026-05-14", styles["Normal"]), table])
    assert parse_pdf_lab_tables(path) is None
