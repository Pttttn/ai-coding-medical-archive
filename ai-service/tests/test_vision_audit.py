from io import BytesIO
import json
import sys

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
import pdfplumber

from medical_ai.vision_audit import compare_rows, lab_header, main, table_png


def test_comparison_flags_numeric_and_unit_conflicts_without_values():
    expected = [["LDL", "<4,1", "mmol/L", "<3.0"]]
    observed = [{"test": "LDL", "result": "4,1", "unit": "mg/dL", "reference": "<3.0"}]
    assert compare_rows(expected, observed) == [
        {"row": 1, "field": "result"}, {"row": 1, "field": "unit"}]
    assert compare_rows(expected, []) == [{"row": None, "field": "row_count"}]
    assert compare_rows(expected, [{"test": "LDL", "result": "<4,1",
                                    "unit": "mmol/L", "reference": "<3.0"}]) == []


def test_rendered_table_is_in_memory_and_has_supported_header():
    output = BytesIO()
    styles = getSampleStyleSheet()
    table = Table([["Test", "Result", "Unit", "Reference"],
                   ["LDL", "4.1", "mmol/L", Paragraph("less than 3.0", styles["Normal"])]],
                  colWidths=[120, 70, 70, 140])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(output).build([table])
    with pdfplumber.open(BytesIO(output.getvalue())) as pdf:
        extracted = next(t for t in pdf.pages[0].find_tables() if lab_header(t.extract()[0]))
        png = table_png(pdf.pages[0], extracted.bbox)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png) > 1000


def test_cli_error_never_prints_private_source_path(monkeypatch, capsys):
    private_path = "C:/private/persons-name.pdf"
    monkeypatch.setattr(sys, "argv", ["vision_audit", "--model", "local", "--runs", "0", private_path])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 1
    output = capsys.readouterr().out
    assert private_path not in output
    assert json.loads(output) == {"status": "ERROR", "code": "AUDIT_UNAVAILABLE"}


def test_audit_labels_matching_two_channels_as_insufficient(tmp_path, monkeypatch):
    import medical_ai.vision_audit as audit_module

    path = tmp_path / 'synthetic.pdf'
    table = Table([['Test', 'Result', 'Unit', 'Reference'],
                   ['LDL', '<4.1', 'mmol/L', '<3.0']], colWidths=[120, 70, 70, 140])
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(str(path)).build([table])

    class Response:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, _route, **_kwargs):
            return Response({'capabilities': ['vision']})

        def get(self, _route):
            return Response({'models': [{'name': 'local', 'digest': 'synthetic', 'size': 1}]})

    monkeypatch.setattr(audit_module.httpx, 'Client', Client)
    monkeypatch.setattr(audit_module, 'read_image', lambda *_args: [
        {'test': 'LDL', 'result': '<4.1', 'unit': 'mmol/L', 'reference': '<3.0'}])
    report = audit_module.audit([path], 'local')
    assert report['passedTables'] == 1
    assert report['checks'][0]['evidenceDecision'] == 'REVIEW_INSUFFICIENT'
    assert '<4.1' not in str(report)
