from medical_ai.archive_qa import complete_excerpt
from medical_ai.rag import verified_excerpt


GLUED_SOURCE = "Метформин не назначался. Аспирин 100 мг назначен ежедневно."


def test_quote_cannot_glue_fragments_into_a_claim_the_source_does_not_make():
    assert verified_excerpt("Метформин\n100 мг назначен", GLUED_SOURCE) is None
    assert complete_excerpt("Метформин\n100 мг назначен", GLUED_SOURCE) is None


def test_separate_lines_must_be_whole_source_lines():
    source = "Метформин не назначался.\nАспирин 100 мг назначен."
    assert verified_excerpt("Метформин\n100 мг назначен", source) is None


def test_separate_lines_must_keep_source_order():
    source = "Аспирин 100 мг назначен.\nМетформин не назначался.\nНаблюдение."
    assert verified_excerpt("Наблюдение.\nАспирин 100 мг назначен.", source) is None


def test_separate_whole_lines_return_the_full_source_span():
    source = "Анамнез:\nМетформин не назначался.\nАллергия не выявлена.\nАспирин 100 мг назначен."
    quote = "Метформин не назначался.\nАспирин 100 мг назначен."
    # The quote shown to the reader keeps the intervening line instead of gluing.
    assert verified_excerpt(quote, source) == (
        "Метформин не назначался.\nАллергия не выявлена.\nАспирин 100 мг назначен.")


def test_public_answer_part_must_be_one_contiguous_source_span(services, provider):
    import pytest

    from medical_ai.errors import ServiceError
    from medical_ai.external_output import PublicOutput

    source = "Метформин не назначался.\nАллергия не выявлена.\nАспирин 100 мг назначен."
    glued = "Метформин не назначался.\nАспирин 100 мг назначен."
    with pytest.raises(ServiceError):
        PublicOutput(services.demo, provider).checked(
            [{"citation": 1, "text": source}], answer=glued,
            answer_parts=[{"citation": 1, "text": glued}])
