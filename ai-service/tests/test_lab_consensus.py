import pytest

from medical_ai.lab_consensus import reconcile_lab_rows


ROW = {'test': 'LDL', 'result': '<4,1', 'unit': 'mmol/L', 'reference': '<3.0'}


def test_three_method_agreement_is_consistent_but_never_accepted():
    report = reconcile_lab_rows({'text_layer': [ROW], 'ocr': [ROW], 'vision': [ROW]}, text_layer_origin='NATIVE')
    assert report['decision'] == 'CONSISTENT_3'
    assert report['issues'] == []
    assert report['automaticallyAccepted'] is False
    assert '<4,1' not in str(report)


def test_two_matching_methods_do_not_form_quorum_even_for_scan():
    for channels in ({'text_layer': [ROW], 'vision': [ROW]},
                     {'ocr': [ROW], 'vision': [ROW]}):
        report = reconcile_lab_rows(channels)
        assert report['decision'] == 'REVIEW_INSUFFICIENT'
        assert report['automaticallyAccepted'] is False


def test_two_against_one_on_critical_field_never_selects_majority_value():
    visual = {**ROW, 'result': '4,1', 'unit': 'mg/dL'}
    report = reconcile_lab_rows({'text_layer': [ROW], 'ocr': [ROW], 'vision': [visual]})
    assert report['decision'] == 'REVIEW_CONFLICT'
    assert report['issues'] == [{'row': 1, 'field': 'result'}, {'row': 1, 'field': 'unit'}]
    assert report['automaticallyAccepted'] is False
    assert 'mg/dL' not in str(report)
    assert '<4,1' not in str(report)


def test_row_alignment_error_stops_field_comparison():
    report = reconcile_lab_rows({'text_layer': [ROW], 'ocr': [], 'vision': [ROW]})
    assert report['decision'] == 'REVIEW_ALIGNMENT'
    assert report['issues'] == [{'row': None, 'field': 'row_count'}]


def test_invalid_evidence_fails_with_fixed_error_without_echoing_values():
    with pytest.raises(ValueError, match='Invalid evidence row') as error:
        reconcile_lab_rows({'vision': [{**ROW, 'result': object()}]})
    assert 'LDL' not in str(error.value)


def test_embedded_ocr_text_layer_does_not_create_false_third_vote():
    channels = {'text_layer': [ROW], 'ocr': [ROW], 'vision': [ROW]}
    assert reconcile_lab_rows(channels)['decision'] == 'REVIEW_INSUFFICIENT'
    assert reconcile_lab_rows(channels, text_layer_origin='OCR_DERIVED')['decision'] == 'REVIEW_INSUFFICIENT'
