"""Author a synthetic lab-only challenge set, independently of model predictions.

Freeze before implementation/evaluation. This is not externally reviewed clinical gold.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'evaluation/ingestion-labs-v1'


def main():
    if ROOT.exists():
        raise SystemExit('Refusing to overwrite the frozen fixture set.')
    ROOT.mkdir(parents=True)
    cases = []
    # Different panels and layouts in development and held-out: not randomized copies.
    panels = [
        [('Гемоглобин', '108', 'г/л', '120–150'), ('MCV', '74,2', 'фл', '80–100'),
         ('Ферритин', '<5,0', 'мкг/л', '15–150'), ('Железо', '6,1', 'мкмоль/л', '9–30'),
         ('Трансферрин', '3,8', 'г/л', '2,0–3,6'), ('СРБ', '2,0', 'мг/л', '<5'),
         ('Лейкоциты', '6,7', '10^9/л', '4–9'), ('Тромбоциты', '410', '10^9/л', '150–400'),
         ('Ретикулоциты', '1,2', '%', '0,5–2,0'), ('B12', '380', 'пг/мл', '')],
        [('ТТГ', '8.4', 'мМЕ/л', '0.4–4.0'), ('Свободный Т4', '9.2', 'пмоль/л', '10–22'),
         ('АТ-ТПО', '>600', 'МЕ/мл', '<35'), ('Натрий', '139', 'ммоль/л', '135–145'),
         ('Калий', '4.2', 'ммоль/л', '3.5–5.1'), ('Кальций', '2.25', 'ммоль/л', '2.15–2.55'),
         ('Альбумин', '42', 'г/л', '35–50'), ('АСТ', '23', 'Ед/л', '<35'),
         ('Билирубин общий', '13', 'мкмоль/л', '5–21'), ('Магний', '0.82', 'ммоль/л', '')],
        [('HbA1c', '≥6,7', '%', '4,0–5,6'), ('Глюкоза плазмы', '7,3', 'ммоль/л', '3,9–5,5'),
         ('Холестерин ЛПВП', '0,9', 'ммоль/л', '>1,0'), ('Холестерин ЛПНП', '3,9', 'ммоль/л', '<3,0'),
         ('Триглицериды', '2,4', 'ммоль/л', '<1,7'), ('Креатинин', '104', 'мкмоль/л', '62–106'),
         ('Мочевина', '7,1', 'ммоль/л', '2,8–8,3'), ('ГГТ', '61', 'Ед/л', '<55'),
         ('АЛТ', '48', 'Ед/л', '0–41'), ('Липопротеин (а)', '≤30', 'мг/дл', '')],
    ]
    held = [
        ('D-димер', '0.62', 'мг/л FEU', '<0.50'), ('Фибриноген', '4.8', 'г/л', '2–4'),
        ('МНО', '1.04', '', '0.8–1.2'), ('АЧТВ', '31', 'с', '25–35'),
        ('Протромбиновое время', '12.8', 'с', '10–14'), ('Антитромбин III', '96', '%', '80–120'),
        ('Тромбиновое время', '17', 'с', '14–21'), ('Протеин C', '82', '%', ''),
        ('Волчаночный антикоагулянт', 'отрицательно', '', ''), ('Тропонин I', '<0.01', 'нг/мл', '<0.04'),
    ]
    for index in range(12):
        split = 'development' if index < 8 else 'held-out'
        folder = ROOT / split
        folder.mkdir(exist_ok=True)
        # Held-out uses tabs and English headers, not either development template.
        layout = 'pipe' if index % 2 == 0 else 'labelled'
        if split == 'held-out':
            layout = 'tsv' if index % 2 == 0 else 'english-pipe'
        panel = panels[index % 3] if split == 'development' else held
        result_date = f'2026-{index + 1:02d}-18'
        specimen_date = f'2026-{index + 1:02d}-17'
        lines = ['Лабораторные исследования', 'СИНТЕТИЧЕСКИЙ пример. Все значения вымышлены.',
                 f'Сценарий: учебная история {index + 1}.', 'Субъект: пациент',
                 f'Дата взятия материала: {specimen_date}', f'Дата результата: {result_date}', '']
        if layout in {'pipe', 'english-pipe'}:
            lines += ['| Показатель | Результат | Единица | Референс |' if layout == 'pipe'
                      else '| Test | Result | Unit | Reference |', '| --- | --- | --- | --- |']
        elif layout == 'tsv':
            lines += ['Test\tResult\tUnit\tReference']
        rows = []
        for name, result, unit, reference in panel:
            if layout in {'pipe', 'english-pipe'}:
                source = f'| {name} | {result} | {unit} | {reference} |'
            elif layout == 'tsv':
                source = '\t'.join([name, result, unit, reference])
            else:
                source = f'{name}: {result} {unit}; референс {reference}; запись лаборатории.'
            lines.append(source)
            rows.append({'name': name, 'resultRaw': result, 'unit': unit or None,
                         'referenceRaw': reference or None, 'resultDate': result_date,
                         'specimenDate': specimen_date, 'subject': 'PATIENT', 'sourceText': source})
        lines += ['', 'Комментарий: отклонение результата не является диагнозом.',
                  'Пример не содержит рекомендаций по лечению.']
        # Real CRLF/NBSP are intentionally represented in source bytes, not only test mocks.
        separator = '\r\n' if index % 3 == 0 else '\n'
        text = separator.join(lines) + separator
        filename = f'{split}/lab-{index + 1:02d}.txt'
        raw = text.encode('utf-8')
        (ROOT / filename).write_bytes(raw)
        cases.append({'id': f'lab-{index + 1:02d}', 'split': split, 'originalFile': filename,
                      'sha256': hashlib.sha256(raw).hexdigest(), 'rows': rows})
    manifest = {'version': 'ingestion-labs-v1', 'synthetic': True,
                'goldReview': 'AI-authored from source templates; no independent clinical review',
                'scope': 'LAB_REPORT only. Held-out layouts/panel excluded from implementation tuning. '
                         'Repeated panels are correlated; 120 rows are not 120 independent clinical cases.',
                'cases': cases}
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
