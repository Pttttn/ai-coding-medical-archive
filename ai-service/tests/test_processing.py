import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from reportlab.pdfgen.canvas import Canvas

from medical_ai.errors import ServiceError
from medical_ai.extraction import extract
from medical_ai.main import create_app
from medical_ai.parsing import parse_file
from medical_ai.privacy import consultation
from medical_ai.schemas import Page


def test_pdf_text_table_and_incomplete_page_warning(tmp_path):
    file = tmp_path / "lab.pdf"
    canvas = Canvas(str(file))
    canvas.drawString(40, 700, "Laboratory table")
    canvas.drawString(40, 680, "LDL     4.1     mmol/L")
    canvas.showPage()
    canvas.showPage()
    canvas.save()
    text, pages, warnings = parse_file(file, 1000000)
    assert "4.1" in text and pages[0].pageNumber == 1
    assert warnings and not pages[1].text


def test_scan_and_malformed_pdf_are_explicit(tmp_path):
    scan = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(scan)
    with pytest.raises(ServiceError) as error:
        parse_file(scan, 1000000)
    assert error.value.code == "UNSUPPORTED_OCR_REQUIRED"
    scan.write_bytes(b"%PDF-not-valid")
    with pytest.raises(ServiceError) as error:
        parse_file(scan, 1000000)
    assert error.value.code == "MALFORMED_PDF"


def test_extraction_validated_source_page(provider):
    result, _ = extract(provider, "lab", [Page(pageNumber=2, text="LDL 4.1 mmol/L")])
    assert result.facts[0].provenance.page == 2
    assert result.documentDate is None


def test_bad_provenance_drops_only_unverified_fact_with_warning(provider):
    provider.fail_quotes = True
    result, warnings = extract(provider, "lab", [Page(text="LDL 4.1 mmol/L")])
    assert result.facts == []
    assert warnings and "цитаты" in warnings[0]
    assert len(provider.calls) == 1


def test_invalid_json_schema_still_retried_and_rejected(provider):
    provider.json = lambda *args, **kwargs: {"documentType": "INVENTED", "summary": "invalid"}
    with pytest.raises(ServiceError) as error:
        extract(provider, "lab", [Page(text="LDL 4.1 mmol/L")])
    assert error.value.code == "EXTRACTION_INVALID"


def test_internal_api_auth_isolation_and_process(services):
    with TestClient(create_app(services)) as client:
        assert client.post("/internal/remove", json={"documentId": "a"}).status_code == 401
        assert client.get("/mcp").status_code == 404
        response = client.post("/internal/process", headers={"X-Internal-Token": "test-secret"},
            json={"documentId": "a", "version": 1, "title": "lab", "text": "LDL 4.1 mmol/L"})
        assert response.status_code == 200
        assert response.json()["extraction"]["facts"][0]["provenance"]["page"] is None


def test_privacy_whole_question_and_context_preserves_clinical_data(provider):
    response = consultation(provider, "Иванов Иван: принимать 5 мг? email name@example.test",
        ["Пациент: Иванов Иван\nДата рождения: 1980-01-02\nНе принимает 10 мг. LDL 4.1 mmol/L. "
         "Файл C:\\data\\uploads\\private.pdf. Телефон +7 999 123-45-67"])
    content = response["content"]
    assert "Иванов" not in content and "name@" not in content and "1980" not in content
    assert "private.pdf" not in content and "+7 999" not in content
    assert "5 мг" in content and "Не принимает 10 мг" in content and "4.1 mmol/L" in content
    assert response["warnings"]



def test_privacy_clinic_same_line_keeps_lab_and_dose(provider):
    result = consultation(provider, "Что значит LDL?", ["Клиника: Тест. LDL 4.73 mmol/L; 5 мг, не 10 мг."])
    assert "4.73 mmol/L" in result["content"] and "не 10 мг" in result["content"]
    assert "Клиника: Тест" not in result["content"]
