import pytest

from medical_ai.chunking import MedicalTextSplitter


def assert_complete_unit(chunks, unit):
    assert any(unit in chunk for chunk in chunks)
    # A repeated overlap must contain the complete medical relation too.
    identifiers = [line.strip() for line in unit.splitlines() if line.strip()]
    for chunk in chunks:
        if any(identifier in chunk for identifier in identifiers):
            assert unit in chunk


@pytest.mark.parametrize("unit", [
    "ЛПНП:\n4.73 ммоль/л.",
    "Препарат ExampleMed:\n2.5 мг один раз в день; факт приёма неизвестен.",
    "Рекомендация: повторить анализ\nчерез 17 дней.",
    "Головокружение\nне отмечается.",
])
def test_fitting_wrapped_medical_paragraph_stays_whole_at_boundary(unit):
    text = "SYNTHETIC introduction. " * 6 + "\n\n" + unit + "\n\n" + "Later note. " * 9
    chunks = MedicalTextSplitter(160, 50).split_text(text)
    assert len(chunks) > 1
    assert_complete_unit(chunks, unit)
    assert all(len(chunk) <= 160 and chunk in text for chunk in chunks)


@pytest.mark.parametrize("unit", [
    "ЛПНП составляет 4.73 ммоль/л.",
    "Препарат ExampleMed: 2.5 мг один раз в день.",
    "Повторный визит рекомендован через 17 дней.",
    "Пациент отрицает головокружение.",
])
def test_sentences_in_long_paragraph_preserve_medical_relation(unit):
    text = "Вводная синтетическая запись. " * 5 + unit + " Следующий осмотр описан отдельно. " * 4
    chunks = MedicalTextSplitter(120, 45).split_text(text)
    assert_complete_unit(chunks, unit)
    assert all(len(chunk) <= 120 and chunk in text for chunk in chunks)


def test_table_rows_are_not_severed_by_chunk_or_overlap():
    rows = ["| Анализ | Значение | Единица |", "|---|---|---|"] + [
        f"| Анализ-{number} | {number}.73 | ммоль/л |" for number in range(12)
    ]
    text = "\n".join(rows)
    chunks = MedicalTextSplitter(125, 40).split_text(text)
    assert len(chunks) > 1
    for row in rows:
        assert any(row in chunk for chunk in chunks)
    for number in range(12):
        for chunk in chunks:
            if f"Анализ-{number} |" in chunk:
                assert rows[number + 2] in chunk
    assert all(len(chunk) <= 125 and chunk in text for chunk in chunks)


def test_wrapped_list_items_preserve_dose_and_deadline():
    items = [
        "- ExampleMed: 2.5 мг\n  один раз в день; приём не подтверждён.",
        "- Повторный анализ\n  через 17 дней после визита.",
        "- Головокружение\n  не отмечается.",
    ]
    text = "\n".join(items)
    chunks = MedicalTextSplitter(100, 35).split_text(text)
    for item in items:
        assert_complete_unit(chunks, item)
    assert all(len(chunk) <= 100 and chunk in text for chunk in chunks)


def test_overlap_repeats_only_complete_units_and_may_be_shorter_than_budget():
    units = ["First statement is complete.", "Second finding is absent.", "Third result is unchanged."]
    text = "\n\n".join(units)
    chunks = MedicalTextSplitter(60, 30).split_text(text)
    assert chunks == ["\n\n".join(units[:2]), "\n\n".join(units[1:])]
    assert MedicalTextSplitter(60, 10).split_text(text) == ["\n\n".join(units[:2]), units[2]]


@pytest.mark.parametrize("text", ["word " * 100, "X" * 411, " " * 180 + "finding " * 60])
def test_explicit_long_unit_fallback_is_bounded_and_loses_no_nonwhitespace(text):
    chunks = MedicalTextSplitter(100).split_text(text)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 100 and chunk in text for chunk in chunks)
    assert "".join("".join(chunk.split()) for chunk in chunks) == "".join(text.split())


def test_empty_text_and_very_large_blank_separators():
    assert MedicalTextSplitter(80, 10).split_text(" \n\n ") == []
    text = "LDL 4.73 mmol/L." + "\n" * 500 + "Dizziness denied."
    assert MedicalTextSplitter(80, 10).split_text(text) == ["LDL 4.73 mmol/L.", "Dizziness denied."]


def test_decimal_and_dose_abbreviation_are_not_sentence_boundaries():
    unit = "Препарат ExampleMed: 2.5 мг. один раз в день."
    text = "Earlier finding is absent. " * 5 + unit + " Later finding is absent. " * 5
    chunks = MedicalTextSplitter(100, 20).split_text(text)
    assert_complete_unit(chunks, unit)
