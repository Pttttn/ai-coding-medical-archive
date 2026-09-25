"""Conservative field-level reconciliation of independent lab table readers.

This does not select a medical value or activate a fact. Each channel represents
one method family; repeated runs of one vision model are never extra votes.
Only safe positions and field names leave this function.
"""
from collections.abc import Mapping, Sequence

FIELDS = ('test', 'result', 'unit', 'reference')
CHANNELS = ('text_layer', 'ocr', 'vision')
MAX_ROWS = 200


def _normalize(value: str) -> str:
    return ' '.join(value.split())


def reconcile_lab_rows(channels: Mapping[str, Sequence[Mapping[str, str]]], *,
                       text_layer_origin: str = 'UNKNOWN') -> dict:
    """Report agreement without choosing a winner or exposing source values.

    Three matching method families mean *consistency*, not verified truth.
    Any missing method, field conflict or row-alignment problem requires review.
    """
    if text_layer_origin not in {'NATIVE', 'OCR_DERIVED', 'UNKNOWN'}:
        raise ValueError('Invalid text layer origin')
    if not channels or any(name not in CHANNELS for name in channels):
        raise ValueError('Invalid evidence channels')
    ordered = [name for name in CHANNELS if name in channels]
    lengths = {}
    for name in ordered:
        rows = channels[name]
        if not isinstance(rows, (list, tuple)) or len(rows) > MAX_ROWS:
            raise ValueError('Invalid evidence rows')
        lengths[name] = len(rows)
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != set(FIELDS) or any(
                not isinstance(row[field], str) or len(row[field]) > 2000 for field in FIELDS
            ):
                raise ValueError('Invalid evidence row')
    report = {'schemaVersion': 'lab-consensus-v1', 'channels': ordered,
              'rowCounts': lengths, 'textLayerOrigin': text_layer_origin,
              'decision': 'REVIEW_INSUFFICIENT',
              'issues': [], 'automaticallyAccepted': False}
    if len(set(lengths.values())) != 1:
        report['decision'] = 'REVIEW_ALIGNMENT'
        report['issues'] = [{'row': None, 'field': 'row_count'}]
        return report
    for index in range(next(iter(lengths.values()))):
        for field in FIELDS:
            values = {_normalize(channels[name][index][field]) for name in ordered}
            if len(values) > 1:
                report['issues'].append({'row': index + 1, 'field': field})
    if report['issues']:
        report['decision'] = 'REVIEW_CONFLICT'
    elif len(ordered) == len(CHANNELS) and lengths[ordered[0]] > 0 and text_layer_origin == 'NATIVE':
        report['decision'] = 'CONSISTENT_3'
    return report
