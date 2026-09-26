"""Privacy scrubbing must never damage medical words (review 2026-09-25, finding 6).

Deterministic providers only: these tests pin the rule layer and the handling of model spans,
not the quality of a real local model.
"""
import pytest

from medical_ai.errors import ServiceError
from medical_ai.privacy import deterministic_sanitize, sanitize_fields


class SpanProvider:
    def __init__(self, *spans):
        self.spans = [{"text": text, "category": category} for text, category in spans]

    def json(self, *args, **kwargs):
        return {"identifiers": self.spans, "warnings": []}


@pytest.mark.parametrize("span", ["ин", "форм", "Метф"])
def test_model_span_inside_a_word_is_rejected_in_strict_mode(span):
    with pytest.raises(ServiceError):
        sanitize_fields(SpanProvider((span, "PERSON")), ["Метформин 500 мг дважды в день."], strict=True)


@pytest.mark.parametrize("span", ["ин", "форм"])
def test_model_span_inside_a_word_never_rewrites_manual_text(span):
    checked = sanitize_fields(SpanProvider((span, "PERSON")), ["Метформин 500 мг дважды в день."])
    assert checked["texts"] == ["Метформин 500 мг дважды в день."]
    assert checked["warnings"]


def test_model_span_is_replaced_only_as_whole_word():
    checked = sanitize_fields(SpanProvider(("Сидоров", "PERSON")),
                              ["Сидоров без жалоб. Сидорова Анна не упоминается как пациент."])
    assert checked["texts"] == ["[PERSON_A] без жалоб. Сидорова Анна не упоминается как пациент."]


@pytest.mark.parametrize("span", ["Stone", "Parkinson"])
def test_model_span_that_is_a_medical_word_is_not_replaced(span):
    text = f"{span} disease follow-up. Kidney {span.lower()} 5 mm."
    with pytest.raises(ServiceError):
        sanitize_fields(SpanProvider((span, "DOCTOR")), [text], strict=True)
    assert sanitize_fields(SpanProvider((span, "DOCTOR")), [text])["texts"] == [text]


def test_model_span_across_two_fields_fails_closed():
    with pytest.raises(ServiceError):
        sanitize_fields(SpanProvider(("Ivanov\nPetr", "PERSON")), ["Seen by Ivanov", "Petr reviewed 5 mg."],
                        strict=True)


def test_model_placeholder_does_not_reuse_rule_placeholder_letter():
    checked = sanitize_fields(SpanProvider(("Olga Primer", "PERSON")),
                              ["Patient: Elena Testova. Olga Primer visited."], strict=True)
    assert checked["texts"] == ["Patient: [PERSON_A]. [PERSON_B] visited."]


def test_doctor_surname_does_not_replace_medical_word():
    text = deterministic_sanitize("Doctor: Mark Stone. Kidney stone 5 mm. Mark reviewed it.")
    assert text == "Doctor: [DOCTOR_A]. Kidney stone 5 mm. [DOCTOR_A] reviewed it."


def test_name_part_is_case_sensitive():
    text = deterministic_sanitize("Patient: Alex Rose. rose bengal test negative. Rose reported no pain.")
    assert "Alex" not in text and "rose bengal test negative" in text


def test_unlabelled_russian_full_name_is_redacted_without_model():
    fields = ["Иванов Пётр Сергеевич, 54 года. Иванов жалоб не предъявляет. Метформин 500 мг.",
              "Пётр Сергеевич Иванов принимает 500 мг."]
    checked = sanitize_fields(SpanProvider(), fields, strict=True)
    joined = "\n".join(checked["texts"])
    assert "Иванов" not in joined and "Пётр" not in joined and "Сергеевич" not in joined
    assert "54 года" in joined and "Метформин 500 мг" in joined and "не предъявляет" in joined


@pytest.mark.parametrize("name", ["Петрова А.С.", "Петрова А. С.", "А.С. Петрова"])
def test_unlabelled_surname_with_initials_is_redacted(name):
    text = deterministic_sanitize(f"Осмотр провела {name}; АД 120/80 мм рт. ст.")
    assert "Петрова" not in text and "120/80 мм рт. ст." in text


@pytest.mark.parametrize("honorific", ["Dr.", "Dr", "Prof."])
def test_name_after_honorific_is_redacted(honorific):
    text = deterministic_sanitize(f"Reviewed by {honorific} Primerov. Primerov advised 2.5 mg daily.")
    assert "Primerov" not in text and "2.5 mg daily" in text


@pytest.mark.parametrize("path", ["/srv/archive/2024/visit.pdf", "sample_docs/notes/visit.txt",
                                  "./private/visit", "~/Documents/labs", "D:\\scans\\labs"])
def test_local_paths_are_masked(path):
    text = deterministic_sanitize(f"Source {path}. LDL 4.73 mmol/L.")
    assert path not in text and "[LOCAL_PATH]. LDL 4.73 mmol/L." in text


@pytest.mark.parametrize("clinical", ["АД 120/80", "5 мг/кг/сут", "10 mg/kg/day", "12/05/2024", "и/или", "mmol/L"])
def test_ratios_units_and_dates_are_not_paths(clinical):
    assert deterministic_sanitize(f"Значение {clinical} без изменений.") == f"Значение {clinical} без изменений."
