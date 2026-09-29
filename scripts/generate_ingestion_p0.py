"""Author the P0 original-upload set: 24 synthetic originals and a separate draft gold.

Every document, value and statement is fictional. Gold is written here from the same
definitions that render the originals, never from any model or parser output. Layouts are
deliberately different from ingestion-labs-v1 / ingestion-visits-v1/v2, which tuned the
current extractors. The set is frozen: the script refuses to overwrite it.

Run from the repository root with the AI dev environment (reportlab):
    cd ai-service && uv run python ../scripts/generate_ingestion_p0.py
"""
import argparse
import hashlib
import json
import textwrap
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'evaluation/ingestion-p0-v1'
SYNTHETIC = 'СИНТЕТИЧЕСКИЙ пример. Все сведения вымышлены.'
QUALITATIVE = {'отрицательно', 'положительно', 'не обнаружено', 'обнаружено', 'negative', 'positive'}

# ---------------------------------------------------------------- LAB definitions
# Each panel: page (1-based), dates by role, rows (test, result as printed, unit, reference).
LABS = [
    dict(id='lab-01', split='development', format='txt', layout='fixed-width columns without separators',
         subject='PATIENT', header=['Лабораторный отчёт', SYNTHETIC, 'Субъект: пациент',
                                    'Дата взятия материала: 03.02.2026', 'Дата результата: 04.02.2026'],
         panels=[dict(page=1, dates={'SPECIMEN': '2026-02-03', 'RESULT': '2026-02-04'}, rows=[
             ('Гемоглобин', '131', 'г/л', '130–160'), ('Эритроциты', '4,38', '10^12/л', '4,0–5,0'),
             ('Гематокрит', '39,5', '%', '40–48'), ('Лейкоциты', '11,2', '10^9/л', '4,0–9,0'),
             ('Нейтрофилы сегментоядерные', '71', '%', '47–72'), ('Лимфоциты', '18', '%', '19–37'),
             ('Моноциты', '7', '%', '3–11'), ('Эозинофилы', '3', '%', '0,5–5'),
             ('Тромбоциты', '265', '10^9/л', '180–320'), ('СОЭ', '24', 'мм/ч', '2–15')])]),
    dict(id='lab-02', split='development', format='md', layout='markdown table, five columns with flag',
         subject='PATIENT', header=['# Лабораторные исследования', '_' + SYNTHETIC + '_',
                                    '**Пациент:** данные скрыты', '**Материал взят:** 2026-02-10 08:15',
                                    '**Результат выдан:** 2026-02-11'],
         panels=[dict(page=1, dates={'SPECIMEN': '2026-02-10', 'RESULT': '2026-02-11'}, rows=[
             ('Глюкоза', '6,4', 'ммоль/л', '3,9–6,1'), ('Креатинин', '118', 'мкмоль/л', '62–106'),
             ('СКФ (CKD-EPI)', '>60', 'мл/мин/1,73м²', '>60'), ('Мочевая кислота', '452', 'мкмоль/л', '202–416'),
             ('Общий белок', '71', 'г/л', '64–83'), ('Альбумин', '44', 'г/л', '35–52'),
             ('Билирубин общий', '9,8', 'мкмоль/л', '3,4–20,5'), ('АЛТ', '<7', 'Ед/л', '<41'),
             ('АСТ', '19', 'Ед/л', '<40'), ('Щелочная фосфатаза', '87', 'Ед/л', '40–129'),
             ('Амилаза', '58', 'Ед/л', '')])]),
    dict(id='lab-03', split='development', format='pdf', layout='PDF grid table over two pages, letterhead, wrapped cells',
         subject='PATIENT', header=['Синтетическая лаборатория «Образец-7»', 'Лабораторные исследования', SYNTHETIC,
                                    'Субъект: пациент', 'Дата взятия материала: 2026-03-05 07:30',
                                    'Дата результата: 2026-03-06 12:00'],
         columns=['Показатель', 'Результат', 'Единица', 'Референс'],
         panels=[dict(page=1, dates={'SPECIMEN': '2026-03-05', 'RESULT': '2026-03-06'}, rows=[
             ('Холестерин общий', '5,9', 'ммоль/л', '<5,2'),
             ('Холестерин липопротеинов высокой плотности', '1,02', 'ммоль/л', '>1,0'),
             ('Холестерин липопротеинов низкой плотности', '3,84', 'ммоль/л', 'желательно <3,0; погранично 3,0–4,1'),
             ('Триглицериды', '1,9', 'ммоль/л', '<1,7'), ('Аполипопротеин A1', '1,31', 'г/л', '1,05–2,05'),
             ('Аполипопротеин B', '1,12', 'г/л', '0,6–1,17'), ('Липопротеин (а)', '74', 'нмоль/л', '<75')]),
                 dict(page=2, dates={'SPECIMEN': '2026-03-05', 'RESULT': '2026-03-06'}, rows=[
             ('Гомоцистеин', '13,8', 'мкмоль/л', '5–15'), ('hs-СРБ', '3,4', 'мг/л', '<1,0'),
             ('Ферритин', '96', 'мкг/л', '30–400'), ('Витамин D (25-OH)', '21,5', 'нг/мл', '30–100'),
             ('NT-proBNP', '88', 'пг/мл', '<125')])]),
    dict(id='lab-04', split='development', format='txt', layout='dash list with unit and parenthesised reference',
         subject='PATIENT', header=['Лабораторные исследования', SYNTHETIC, 'Обследуемый: пациент',
                                    'Дата исследования: 12.03.2026'],
         panels=[dict(page=1, dates={'STUDY': '2026-03-12'}, rows=[
             ('Глюкоза', '99', 'мг/дл', '70–99'), ('Холестерин общий', '212', 'мг/дл', '<200'),
             ('Холестерин ЛПНП', '138', 'мг/дл', '<130'), ('Холестерин ЛПВП', '47', 'мг/дл', '>40'),
             ('Триглицериды', '135', 'мг/дл', '<150'), ('Креатинин', '1,05', 'мг/дл', '0,7–1,2'),
             ('Мочевина', '31', 'мг/дл', '17–43'), ('Кальций общий', '9,6', 'мг/дл', '8,6–10,3'),
             ('Калий', '4,4', 'ммоль/л', '3,5–5,1'), ('Инсулин', '14,2', 'мкЕд/мл', '')])]),
    dict(id='lab-05', split='development', format='pdf', layout='PDF, two panels with different specimen dates, repeated tests',
         subject='PATIENT', header=['Лабораторные исследования', SYNTHETIC, 'Субъект: пациент'],
         columns=['Показатель', 'Результат', 'Единица', 'Референс'],
         panels=[dict(page=1, caption=['Панель 1', 'Дата взятия материала: 2026-04-01', 'Дата результата: 2026-04-02'],
                      dates={'SPECIMEN': '2026-04-01', 'RESULT': '2026-04-02'}, rows=[
             ('Железо сывороточное', '7,4', 'мкмоль/л', '10,7–32,2'), ('ОЖСС', '78', 'мкмоль/л', '45–77'),
             ('Ферритин', '9', 'мкг/л', '15–150'), ('Трансферрин', '3,9', 'г/л', '2,0–3,6'),
             ('Витамин B12', '162', 'пг/мл', '187–883')]),
                 dict(page=1, caption=['Панель 2', 'Дата взятия материала: 2026-04-08', 'Дата результата: 2026-04-09'],
                      dates={'SPECIMEN': '2026-04-08', 'RESULT': '2026-04-09'}, rows=[
             ('Железо сывороточное', '9,1', 'мкмоль/л', '10,7–32,2'), ('Ферритин', '11', 'мкг/л', '15–150'),
             ('Гемоглобин', '112', 'г/л', '120–140'), ('Ретикулоциты', '2,4', '%', '0,5–1,5'),
             ('Фолиевая кислота', '>20', 'нг/мл', '3,1–20,5')])]),
    dict(id='lab-06', split='development', format='txt', layout='pipe table, results of a family member',
         subject='FAMILY', header=['Лабораторные исследования', SYNTHETIC,
                                   'Субъект: мать пациента (приложено для семейного анамнеза)',
                                   'Дата результата: 2026-01-20'],
         panels=[dict(page=1, dates={'RESULT': '2026-01-20'}, rows=[
             ('ТТГ', '6,8', 'мМЕ/л', '0,4–4,0'), ('Свободный Т4', '10,1', 'пмоль/л', '9–19'),
             ('АТ-ТПО', '>1000', 'МЕ/мл', '<34'), ('АТ к рецептору ТТГ', '<0,8', 'МЕ/л', '<1,75'),
             ('Тиреоглобулин', '3,2', 'нг/мл', '3,5–77'), ('Кальцитонин', '<2', 'пг/мл', '<6,4'),
             ('Пролактин', '312', 'мМЕ/л', '102–496'), ('Кортизол', '455', 'нмоль/л', '171–536'),
             ('Антитела к тиреоглобулину', 'отрицательно', '', ''), ('Паратгормон', '5,1', 'пмоль/л', '')])]),
    # ------------------------------------------------------------ held-out: never used for tuning
    dict(id='lab-07', split='held-out', format='pdf', layout='PDF, two tables side by side on one page',
         subject='PATIENT', header=['Лабораторные исследования', SYNTHETIC, 'Субъект: пациент',
                                    'Дата взятия материала: 2026-05-14', 'Дата результата: 2026-05-15'],
         columns=['Показатель', 'Результат', 'Единица', 'Референс'],
         panels=[dict(page=1, caption=['Общий анализ мочи'], dates={'SPECIMEN': '2026-05-14', 'RESULT': '2026-05-15'}, rows=[
             ('Удельный вес', '1,028', '', '1,010–1,025'), ('pH', '5,5', '', '5,0–7,0'),
             ('Белок', '0,3', 'г/л', '<0,14'), ('Глюкоза', 'не обнаружено', '', 'не обнаружено'),
             ('Лейкоциты', '3', 'в п/з', '0–5')]),
                 dict(page=1, caption=['Биохимия мочи'], dates={'SPECIMEN': '2026-05-14', 'RESULT': '2026-05-15'}, rows=[
             ('Альбумин/креатинин', '4,1', 'мг/ммоль', '<3,0'), ('Креатинин мочи', '12,4', 'ммоль/л', ''),
             ('Натрий мочи', '146', 'ммоль/сут', '40–220'), ('Калий мочи', '58', 'ммоль/сут', '25–125'),
             ('Кальций мочи', '6,8', 'ммоль/сут', '2,5–7,5')])]),
    dict(id='lab-08', split='held-out', format='md', layout='English markdown table with different headers',
         subject='PATIENT', header=['# Laboratory report', '_Synthetic example. All values are fictional._',
                                    'Subject: patient', 'Specimen collected: 2026-06-03 09:10', 'Reported: 2026-06-04'],
         panels=[dict(page=1, dates={'SPECIMEN': '2026-06-03', 'RESULT': '2026-06-04'}, rows=[
             ('Hemoglobin A1c', '7.2', '%', '4.0–5.6'), ('Fasting glucose', '8.1', 'mmol/L', '3.9–5.5'),
             ('C-peptide', '0.42', 'nmol/L', '0.37–1.47'), ('Microalbumin', '>150', 'mg/L', '<20'),
             ('eGFR', '74', 'mL/min/1.73m²', '>90'), ('Cystatin C', '1.09', 'mg/L', '0.61–0.95'),
             ('GAD antibodies', 'negative', '', ''), ('Ketones (urine)', 'negative', '', 'negative'),
             ('Lactate', '1.6', 'mmol/L', '0.5–2.2'), ('Uric acid', '6.9', 'mg/dL', '3.5–7.2')])]),
    dict(id='lab-09', split='held-out', format='txt', layout='pipe table with wrapped test names and page break',
         subject='PATIENT', header=['Лабораторные исследования', SYNTHETIC, 'Субъект: пациент',
                                    'Дата взятия материала: 21.06.2026', 'Дата результата: 22.06.2026'],
         panels=[dict(page=1, dates={'SPECIMEN': '2026-06-21', 'RESULT': '2026-06-22'}, rows=[
             ('Холестерин липопротеинов низкой плотности', '4,6', 'ммоль/л', '<3,0'),
             ('Холестерин общий', '6,8', 'ммоль/л', '<5,2'), ('Триглицериды', '2,9', 'ммоль/л', '<1,7'),
             ('Коэффициент атерогенности', '4,1', '', '<3,0'), ('Глюкоза', '5,8', 'ммоль/л', '4,1–5,9'),
             ('Гликированный гемоглобин', '6,1', '%', '<6,0'),
             ('Аланинаминотрансфераза (АЛТ)', '62', 'Ед/л', '<41'),
             ('Аспартатаминотрансфераза (АСТ)', '44', 'Ед/л', '<40'),
             ('Гамма-глутамилтрансфераза', '97', 'Ед/л', '10–71'), ('Билирубин прямой', '4,1', 'мкмоль/л', '<5,0'),
             ('Щелочная фосфатаза', '101', 'Ед/л', '40–129')])]),
    dict(id='lab-10', split='held-out', format='pdf', layout='PDF over three pages, running header/footer, other column names',
         subject='PATIENT', header=['Результаты лабораторных исследований', SYNTHETIC,
                                    'Пациент: вымышленный', 'Дата и время взятия биоматериала: 2026-07-02 08:05',
                                    'Дата выдачи результата: 2026-07-03'],
         columns=['Исследование', 'Результат', 'Единицы', 'Референсные значения'],
         panels=[dict(page=1, dates={'SPECIMEN': '2026-07-02', 'RESULT': '2026-07-03'}, rows=[
             ('ТТГ', '2,31', 'мкМЕ/мл', '0,4–4,0'), ('Т4 свободный', '14,6', 'пмоль/л', '9–19'),
             ('Т3 свободный', '4,9', 'пмоль/л', '2,6–5,7'), ('Антитела к ТПО', '<5', 'МЕ/мл', '<34')]),
                 dict(page=2, dates={'SPECIMEN': '2026-07-02', 'RESULT': '2026-07-03'}, rows=[
             ('Эстрадиол', '412', 'пмоль/л', 'зависит от фазы цикла'), ('ЛГ', '7,8', 'мМЕ/мл', '2,4–12,6'),
             ('ФСГ', '6,1', 'мМЕ/мл', '3,5–12,5'), ('Прогестерон', '1,2', 'нмоль/л', '')]),
                 dict(page=3, dates={'SPECIMEN': '2026-07-02', 'RESULT': '2026-07-03'}, rows=[
             ('Витамин B12', '518', 'пг/мл', '187–883'), ('Витамин D (25-OH)', '38,4', 'нг/мл', '30–100'),
             ('Цинк', '11,9', 'мкмоль/л', '10,7–18,4')])]),
    dict(id='lab-11', split='held-out', format='txt', layout='labelled lines with ×10⁹ units, thousands separator, flags',
         subject='PATIENT', header=['Лабораторные исследования', SYNTHETIC, 'Субъект: пациент',
                                    'Дата взятия материала: 2026-08-10', 'Дата результата: 2026-08-11'],
         panels=[dict(page=1, dates={'SPECIMEN': '2026-08-10', 'RESULT': '2026-08-11'}, rows=[
             ('Лейкоциты', '5,6', '×10⁹/л', '4,0–9,0'), ('Нейтрофилы абс.', '3,4', '×10⁹/л', '1,8–7,7'),
             ('D-димер', '1 250', 'нг/мл FEU', '<500'), ('Прокальцитонин', '<0,05', 'нг/мл', '<0,5'),
             ('СРБ', '12,6', 'мг/л', '0–5'), ('Фибриноген', '4,1', 'г/л', '2,0–4,0'),
             ('МНО', '1,12', '', '0,85–1,15'), ('Лактатдегидрогеназа', '245', 'Ед/л', '135–225'),
             ('Ферритин', '380', 'мкг/л', '30–400'), ('Интерлейкин-6', '4,2', 'пг/мл', 'не установлен'),
             ('Тропонин T высокочувствительный', '9', 'нг/л', '<14')])]),
    dict(id='lab-12', split='held-out', format='md', layout='markdown bullets, no subject, specimen date only',
         subject='UNKNOWN', header=['## Результаты анализов', '_' + SYNTHETIC + '_',
                                    'Принадлежность бланка не указана.', 'Дата взятия: 2026-09-01'],
         panels=[dict(page=1, dates={'SPECIMEN': '2026-09-01'}, rows=[
             ('Ферритин', '12', 'мкг/л', '15–150'), ('Железо', '8,2', 'мкмоль/л', '9–30,4'),
             ('Трансферрин', '3,7', 'г/л', '2,0–3,6'), ('Насыщение трансферрина железом', '11', '%', '20–50'),
             ('Витамин B12', '205', 'пг/мл', '187–883'), ('Фолиевая кислота', '4,3', 'нг/мл', '3,1–20,5'),
             ('Гемоглобин', '109', 'г/л', '120–140'), ('MCV', '76', 'фл', '80–100'), ('MCH', '24,1', 'пг', '27–31'),
             ('RDW-CV', '16,8', '%', '11,5–14,5'), ('Гепсидин', '3,1', 'нг/мл', '')])]),
]

# ---------------------------------------------------------------- VISIT definitions
# Statement shorthand: (name as printed, kind, subject, assertion, medicationState, temporality).
C, S, M = 'CONDITION', 'SYMPTOM', 'MEDICATION'
NA = 'NOT_APPLICABLE'


def st(name, kind, assertion, state=NA, temporality='CURRENT', subject='PATIENT'):
    return dict(name=name, kind=kind, subject=subject, assertion=assertion if kind != M else 'UNKNOWN',
                medicationState=state if kind == M else NA, temporality=temporality)


def med(name, state, temporality='CURRENT', subject='PATIENT'):
    return st(name, M, 'UNKNOWN', state, temporality, subject)


VISITS = [
    dict(id='visit-01', split='development', format='txt', layout='prose sections, two dates, doses', pages=[[
        ('p', ['Приём терапевта.', SYNTHETIC, 'Дата приёма: 14.01.2026.', 'Предыдущий визит: 02.12.2025.']),
        ('h', 'Жалобы'),
        ('p', [('Пациент жалуется на изжогу после еды в течение трёх недель.', [st('изжогу', S, 'CONFIRMED')]),
               ('Боли за грудиной при нагрузке пациент отрицает.', [st('Боли за грудиной', S, 'NEGATED')])]),
        ('h', 'Анамнез'),
        ('p', [('В 2021 году у пациента диагностирована язвенная болезнь двенадцатиперстной кишки.',
                [st('язвенная болезнь двенадцатиперстной кишки', C, 'CONFIRMED', temporality='HISTORICAL')]),
               ('У матери пациента рак желудка выявлен в 58 лет.',
                [st('рак желудка', C, 'CONFIRMED', temporality='HISTORICAL', subject='FAMILY')])]),
        ('h', 'Заключение и назначения'),
        ('p', [('Предварительно: гастроэзофагеальная рефлюксная болезнь, требуется подтверждение после ФГДС.',
                [st('гастроэзофагеальная рефлюксная болезнь', C, 'SUSPECTED')]),
               ('Назначен омепразол 20 мг 2 раза в день за 30 минут до еды на 4 недели.', [med('омепразол', 'PRESCRIBED')]),
               ('Ранее принимавшийся ибупрофен 400 мг отменён.', [med('ибупрофен', 'STOPPED')])])]]),
    dict(id='visit-02', split='development', format='md', layout='markdown headings and bullets', pages=[[
        ('title', 'Консультация кардиолога'),
        ('p', ['_' + SYNTHETIC + '_', 'Дата консультации: 2026-02-18; дата ЭКГ: 2026-02-16.']),
        ('h', 'Жалобы'),
        ('ul', [('Периодическое сердцебиение по вечерам.', [st('сердцебиение', S, 'CONFIRMED')]),
                ('Одышка при нагрузке не беспокоит.', [st('Одышка', S, 'NEGATED')])]),
        ('h', 'Анамнез'),
        ('ul', [('Гипертоническая болезнь с 2018 года, наблюдается постоянно.', [st('Гипертоническая болезнь', C, 'CONFIRMED')]),
                ('У отца инфаркт миокарда в 52 года.',
                 [st('инфаркт миокарда', C, 'CONFIRMED', temporality='HISTORICAL', subject='FAMILY')]),
                ('У брата пациента фибрилляция предсердий не подтверждена.',
                 [st('фибрилляция предсердий', C, 'NOT_CONFIRMED', subject='FAMILY')])]),
        ('h', 'План'),
        ('ul', [('Бисопролол 2,5 мг утром принимает регулярно, продолжить.', [med('Бисопролол', 'TAKING')]),
                ('Аторвастатин 20 мг назначен, пациент пока не начал приём.', [med('Аторвастатин', 'NOT_STARTED')]),
                ('Пароксизмальная тахикардия предполагается, назначено суточное мониторирование ЭКГ.',
                 [st('Пароксизмальная тахикардия', C, 'SUSPECTED')])])]]),
    dict(id='visit-03', split='development', format='pdf', layout='PDF over two pages', pages=[[
        ('p', ['Осмотр невролога.', SYNTHETIC, 'Дата осмотра: 05.03.2026.']),
        ('p', [('Пациент отмечает головные боли давящего характера 2–3 раза в неделю.', [st('головные боли', S, 'CONFIRMED')]),
               ('Тошнота на высоте головной боли отсутствует.', [st('Тошнота', S, 'NEGATED')]),
               ('Онемение в левой руке было в ноябре 2025 года, сейчас не повторяется.',
                [st('Онемение в левой руке', S, 'CONFIRMED', temporality='HISTORICAL')])]),
        ('p', [('У сестры пациента мигрень с аурой подтверждена неврологом.',
                [st('мигрень с аурой', C, 'CONFIRMED', subject='FAMILY')])])], [
        ('p', [('Мигрень без ауры у пациента не исключена, но критериев недостаточно.', [st('Мигрень без ауры', C, 'SUSPECTED')]),
               ('Рассеянный склероз по данным МРТ исключён.', [st('Рассеянный склероз', C, 'RULED_OUT')])]),
        ('p', [('Амитриптилин 10 мг на ночь назначен с понедельника.', [med('Амитриптилин', 'PRESCRIBED', 'FUTURE')]),
               ('Суматриптан 50 мг пациент принимал в 2024 году, прекратил из-за побочных эффектов.',
                [med('Суматриптан', 'STOPPED', 'HISTORICAL')])])]]),
    dict(id='visit-04', split='development', format='txt', layout='hard-wrapped lines inside sentences', wrap=64, pages=[[
        ('p', ['Приём эндокринолога.', SYNTHETIC, 'Дата приёма: 22.04.2026.']),
        ('p', [('Сахарный диабет 2 типа диагностирован в 2019 году и остаётся под наблюдением.',
                [st('Сахарный диабет 2 типа', C, 'CONFIRMED')]),
               ('Жажда и учащённое мочеиспускание в последний месяц не отмечаются.',
                [st('Жажда', S, 'NEGATED'), st('учащённое мочеиспускание', S, 'NEGATED')]),
               ('Диабетическая ретинопатия не подтверждена при осмотре окулиста.',
                [st('Диабетическая ретинопатия', C, 'NOT_CONFIRMED')])]),
        ('p', [('Пациент принимает метформин 1000 мг 2 раза в день.', [med('метформин', 'TAKING')]),
               ('Эмпаглифлозин 10 мг был назначен в марте и отменён через две недели.',
                [med('Эмпаглифлозин', 'STOPPED', 'HISTORICAL')]),
               ('У матери пациента сахарный диабет 2 типа.', [st('сахарный диабет 2 типа', C, 'CONFIRMED', subject='FAMILY')])])]]),
    dict(id='visit-05', split='development', format='txt', layout='telephone note without a visit heading', pages=[[
        ('p', ['Запись телефонного разговора с пациентом.', SYNTHETIC, 'Дата звонка: 30.04.2026.']),
        ('p', [('Пациент сообщает, что кашель прошёл неделю назад.', [st('кашель', S, 'CONFIRMED', temporality='HISTORICAL')]),
               ('Лихорадка отсутствует.', [st('Лихорадка', S, 'NEGATED')]),
               ('Амоксициллин 500 мг пациент допил полностью, курс завершён.', [med('Амоксициллин', 'STOPPED', 'HISTORICAL')])]),
        ('p', [('Пневмония по контрольному снимку исключена.', [st('Пневмония', C, 'RULED_OUT')]),
               ('Ацетилцистеин рекомендован, но пациент его не начинал.', [med('Ацетилцистеин', 'NOT_STARTED')]),
               ('У супруги пациента сейчас бронхит.', [st('бронхит', C, 'CONFIRMED', subject='OTHER')])])]]),
    dict(id='visit-06', split='development', format='md', layout='markdown bullets, biopsy date', pages=[[
        ('title', 'Осмотр дерматолога'),
        ('p', ['_' + SYNTHETIC + '_', 'Дата осмотра: 2026-05-12. Дата биопсии: 2026-05-05.']),
        ('h', 'Статус'),
        ('ul', [('Атопический дерматит был в детстве.', [st('Атопический дерматит', C, 'CONFIRMED', temporality='HISTORICAL')]),
                ('Зуд беспокоит по ночам.', [st('Зуд', S, 'CONFIRMED')]),
                ('Псориаз у пациента подозревается, ждём гистологию.', [st('Псориаз', C, 'SUSPECTED')]),
                ('Микоз стоп по посеву не подтверждён.', [st('Микоз стоп', C, 'NOT_CONFIRMED')]),
                ('У дочери пациента псориаз подтверждён.', [st('псориаз', C, 'CONFIRMED', subject='FAMILY')])]),
        ('h', 'Назначения'),
        ('ul', [('Мометазон крем 0,1% 1 раз в день на 14 дней назначен.', [med('Мометазон', 'PRESCRIBED')]),
                ('Цетиризин 10 мг пациент принимает сам последние две недели.', [med('Цетиризин', 'TAKING')])])]]),
    # ------------------------------------------------------------ held-out: never used for tuning
    dict(id='visit-07', split='held-out', format='pdf', layout='PDF with two text columns', columns=2, pages=[[
        ('p', ['Консультация гастроэнтеролога.', SYNTHETIC, 'Дата: 03.06.2026.']),
        ('p', [('Пациент жалуется на вздутие живота после молочных продуктов.', [st('вздутие живота', S, 'CONFIRMED')]),
               ('Кровь в стуле пациент отрицает.', [st('Кровь в стуле', S, 'NEGATED')])]),
        ('p', [('Целиакия по данным серологии исключена.', [st('Целиакия', C, 'RULED_OUT')]),
               ('Лактазная недостаточность предполагается.', [st('Лактазная недостаточность', C, 'SUSPECTED')])]),
        ('p', [('У отца пациента болезнь Крона.', [st('болезнь Крона', C, 'CONFIRMED', subject='FAMILY')])]),
        ('p', [('Мебеверин 200 мг 2 раза в день назначен на 4 недели.', [med('Мебеверин', 'PRESCRIBED')]),
               ('Пантопразол пациент перестал принимать в мае.', [med('Пантопразол', 'STOPPED', 'HISTORICAL')])])]]),
    dict(id='visit-08', split='held-out', format='md', layout='English clinical note', pages=[[
        ('title', 'Clinical note: cardiology follow-up'),
        ('p', ['_Synthetic example. All details are fictional._', 'Visit date: 2026-06-17.']),
        ('ul', [('The patient reports intermittent palpitations.', [st('palpitations', S, 'CONFIRMED')]),
                ('Chest pain is denied.', [st('Chest pain', S, 'NEGATED')]),
                ('Atrial fibrillation was ruled out on Holter monitoring.', [st('Atrial fibrillation', C, 'RULED_OUT')]),
                ('Hypothyroidism is suspected; TSH is pending.', [st('Hypothyroidism', C, 'SUSPECTED')]),
                ("The patient's mother has atrial fibrillation.",
                 [st('atrial fibrillation', C, 'CONFIRMED', subject='FAMILY')]),
                ('Metoprolol 25 mg was prescribed but not started.', [med('Metoprolol', 'NOT_STARTED')]),
                ('Aspirin 75 mg was discontinued last year.', [med('Aspirin', 'STOPPED', 'HISTORICAL')])])]]),
    dict(id='visit-09', split='held-out', format='txt', layout='outpatient extract, period and extract date', pages=[[
        ('p', ['Выписка из амбулаторной карты.', SYNTHETIC, 'Дата выписки: 15.07.2026.', 'Период: 01.2025–07.2026.']),
        ('p', [('Бронхиальная астма установлена в 2015 году, в настоящее время контролируемая.',
                [st('Бронхиальная астма', C, 'CONFIRMED')]),
               ('Приступы удушья за последний год не отмечались.', [st('Приступы удушья', S, 'NEGATED')]),
               ('Аллергический ринит у пациента предполагается по сезонности симптомов.',
                [st('Аллергический ринит', C, 'SUSPECTED')])]),
        ('p', [('У бабушки пациента по материнской линии была бронхиальная астма.',
                [st('бронхиальная астма', C, 'CONFIRMED', temporality='HISTORICAL', subject='FAMILY')])]),
        ('p', [('Будесонид/формотерол 160/4,5 мкг по 1 вдоху 2 раза в день пациент получает постоянно.',
                [med('Будесонид/формотерол', 'TAKING')]),
               ('Монтелукаст 10 мг отменён в марте 2026 года.', [med('Монтелукаст', 'STOPPED', 'HISTORICAL')]),
               ('Сальбутамол по потребности назначен, пациент не использовал ни разу.', [med('Сальбутамол', 'NOT_STARTED')])])]]),
    dict(id='visit-10', split='held-out', format='pdf', layout='PDF, narrow column over two pages', narrow=True, pages=[[
        ('p', ['Приём ревматолога.', SYNTHETIC, 'Дата приёма: 11.08.2026.']),
        ('p', [('Боли в мелких суставах кистей беспокоят около двух месяцев.',
                [st('Боли в мелких суставах кистей', S, 'CONFIRMED')]),
               ('Утренняя скованность отсутствует.', [st('Утренняя скованность', S, 'NEGATED')])]),
        ('p', [('Ревматоидный артрит пока не подтверждён, ожидаются результаты АЦЦП.',
                [st('Ревматоидный артрит', C, 'NOT_CONFIRMED')]),
               ('Подагра у пациента исключена.', [st('Подагра', C, 'RULED_OUT')])])], [
        ('p', [('У тёти пациента системная красная волчанка.',
                [st('системная красная волчанка', C, 'CONFIRMED', subject='FAMILY')]),
               ('Нимесулид 100 мг пациент принимал до июля, сейчас не принимает.',
                [med('Нимесулид', 'STOPPED', 'HISTORICAL')]),
               ('Гидроксихлорохин 200 мг назначен с 15.08.2026.', [med('Гидроксихлорохин', 'PRESCRIBED', 'FUTURE')])])]]),
    dict(id='visit-11', split='held-out', format='txt', layout='patient diary in first person, no visit heading', pages=[[
        ('p', ['Дневник самонаблюдения, записи пациента.', SYNTHETIC, 'Период: 01.09.2026–07.09.2026.']),
        ('p', [('Бессонница сохраняется почти каждую ночь.', [st('Бессонница', S, 'CONFIRMED')]),
               ('Тревожность стала меньше.', [st('Тревожность', S, 'CONFIRMED')])]),
        ('p', [('Мелатонин 3 мг принимаю на ночь с 2 сентября.', [med('Мелатонин', 'TAKING')]),
               ('Золпидем врач выписал, но я его не начинал.', [med('Золпидем', 'NOT_STARTED')])]),
        ('p', [('У мамы давно депрессия, она лечится.', [st('депрессия', C, 'CONFIRMED', subject='FAMILY')]),
               ('Панические атаки на этой неделе не повторялись.', [st('Панические атаки', S, 'NEGATED')])])]]),
    dict(id='visit-12', split='held-out', format='md', layout='markdown bullets and a medication table', pages=[[
        ('title', 'Приём уролога'),
        ('p', ['_' + SYNTHETIC + '_', 'Дата приёма: 2026-09-09; дата УЗИ: 2026-09-01.']),
        ('h', 'Жалобы и анамнез'),
        ('ul', [('Учащённое ночное мочеиспускание до 3 раз за ночь.', [st('Учащённое ночное мочеиспускание', S, 'CONFIRMED')]),
                ('Боли при мочеиспускании нет.', [st('Боли при мочеиспускании', S, 'NEGATED')]),
                ('Мочекаменная болезнь в 2022 году, камень отошёл самостоятельно.',
                 [st('Мочекаменная болезнь', C, 'CONFIRMED', temporality='HISTORICAL')]),
                ('Доброкачественная гиперплазия предстательной железы предполагается по УЗИ.',
                 [st('Доброкачественная гиперплазия предстательной железы', C, 'SUSPECTED')]),
                ('У отца пациента рак предстательной железы.',
                 [st('рак предстательной железы', C, 'CONFIRMED', subject='FAMILY')])]),
        ('h', 'Лекарства'),
        ('table', ['Препарат', 'Доза', 'Статус'], [
            (['Тамсулозин', '0,4 мг на ночь', 'принимает'], [med('Тамсулозин', 'TAKING')]),
            (['Финастерид', '5 мг утром', 'назначен, не начат'], [med('Финастерид', 'NOT_STARTED')]),
            (['Доксазозин', '2 мг', 'отменён в 2026-08'], [med('Доксазозин', 'STOPPED', 'HISTORICAL')])])]]),
]


# ---------------------------------------------------------------- gold derivation
def result_fields(raw):
    """Printed result → kind, comparator, exact decimal. Thousands spaces are not decimals."""
    if raw.casefold() in QUALITATIVE:
        return 'QUALITATIVE', None, None
    comparator = next((c for c in ('<=', '>=', '≤', '≥', '<', '>') if raw.startswith(c)), '')
    number = raw[len(comparator):].replace(' ', '').replace(',', '.')
    return 'NUMERIC', {'≤': '<=', '≥': '>='}.get(comparator, comparator) or '=', str(Decimal(number))


def lab_gold(case):
    rows = []
    for panel in case['panels']:
        for test, result, unit, reference in panel['rows']:
            kind, comparator, value = result_fields(result)
            rows.append(dict(test=test, result=result, kind=kind, comparator=comparator, value=value,
                             unit=unit or None, reference=reference or None, dates=dict(panel['dates']),
                             subject=case['subject'], page=panel['page']))
    return rows


def md_row(cells):
    return '| ' + ' | '.join(cells) + ' |'


def visit_items(block):
    kind = block[0]
    if kind == 'table':
        return [(md_row(cells), stmts) for cells, stmts in block[2]]
    if kind in ('p', 'ul'):
        return [item if isinstance(item, tuple) else (item, []) for item in block[1]]
    return []


def visit_gold(case):
    out = []
    for page_number, page in enumerate(case['pages'], 1):
        for block in page:
            for sentence, statements in visit_items(block):
                for statement in statements:
                    assert statement['name'] in sentence, (case['id'], statement['name'])
                    out.append({**statement, 'sourceText': sentence, 'page': page_number})
    return out


# ---------------------------------------------------------------- rendering: text
def render_lab_text(case):
    lines = list(case['header']) + ['']
    rows = [r for p in case['panels'] for r in p['rows']]
    layout = case['id']
    if layout == 'lab-01':
        lines.append(f"{'Показатель':<30}{'Результат':>10}  {'Ед.':<10}Референс")
        lines += [f'{t:<30}{r:>10}  {u:<10}{ref}'.rstrip() for t, r, u, ref in rows]
    elif layout == 'lab-02':
        lines += [md_row(['Показатель', 'Результат', 'Единицы', 'Референсный интервал', 'Отметка']),
                  md_row(['---'] * 5)]
        flags = {'Глюкоза': '↑', 'Креатинин': '↑', 'Мочевая кислота': '↑'}
        lines += [md_row([t, r, u, ref, flags.get(t, '')]) for t, r, u, ref in rows]
    elif layout == 'lab-04':
        lines += [f'{t} — {r} {u}' + (f' (реф. {ref})' if ref else '') for t, r, u, ref in rows]
    elif layout == 'lab-06':
        lines += [md_row(['Показатель', 'Результат', 'Единица', 'Референс']), md_row(['---'] * 4)]
        lines += [md_row([t, r, u, ref]) for t, r, u, ref in rows]
    elif layout == 'lab-08':
        lines += [md_row(['Analyte', 'Value', 'Units', 'Ref. range']), md_row(['---'] * 4)]
        lines += [md_row([t, r, u, ref]) for t, r, u, ref in rows]
    elif layout == 'lab-09':
        wraps = {'Холестерин липопротеинов низкой плотности': ('Холестерин липопротеинов', 'низкой плотности'),
                 'Коэффициент атерогенности': ('Коэффициент', 'атерогенности'),
                 'Аспартатаминотрансфераза (АСТ)': ('Аспартатаминотрансфераза', '(АСТ)')}
        head = [md_row(['Показатель', 'Результат', 'Единица', 'Референс']), md_row(['---'] * 4)]
        lines += head
        for index, (t, r, u, ref) in enumerate(rows):
            if index == 6:
                lines += ['', '— Страница 1 из 2 —', '', 'Лабораторные исследования (продолжение)', ''] + head
            first, rest = wraps.get(t, (t, None))
            lines.append(md_row([first, r, u, ref]))
            if rest:
                lines.append(md_row([rest, '', '', '']))
        lines += ['', '— Страница 2 из 2 —']
    elif layout == 'lab-11':
        flags = {'СРБ': 'повышен', 'Фибриноген': 'повышен', 'Лактатдегидрогеназа': 'повышен', 'D-димер': 'повышен'}
        for t, r, u, ref in rows:
            line = f'{t}: {r}' + (f' {u}' if u else '') + f'; референс {ref}'
            lines.append(line + (f'; {flags[t]}' if t in flags else ''))
    elif layout == 'lab-12':
        lines += [f'- **{t}**: {r} {u}' + (f' (норма {ref})' if ref else '') for t, r, u, ref in rows]
    else:
        raise ValueError(layout)
    lines += ['', 'Комментарий: отклонение результата не является диагнозом.']
    return '\n'.join(lines) + '\n'


def render_visit_text(case):
    markdown = case['format'] == 'md'
    parts = []
    for block in case['pages'][0]:
        kind = block[0]
        if kind == 'title':
            parts.append('# ' + block[1])
        elif kind == 'h':
            parts.append(('## ' if markdown else '') + block[1] + ('' if markdown else ':'))
        elif kind == 'p':
            text = ' '.join(sentence for sentence, _ in visit_items(block))
            parts.append('\n'.join(textwrap.wrap(text, case['wrap'])) if case.get('wrap') else text)
        elif kind == 'ul':
            parts.append('\n'.join('- ' + sentence for sentence, _ in visit_items(block)))
        elif kind == 'table':
            parts.append('\n'.join([md_row(block[1]), md_row(['---'] * len(block[1]))]
                                   + [sentence for sentence, _ in visit_items(block)]))
    return '\n\n'.join(parts) + '\n'


# ---------------------------------------------------------------- rendering: PDF
def pdf_tools(font):
    from reportlab import rl_config
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    rl_config.invariant = 1  # Reproducible bytes: no creation timestamp or random document ID.
    pdfmetrics.registerFont(TTFont('Synthetic', str(font)))
    body = ParagraphStyle('SyntheticBody', fontName='Synthetic', fontSize=10, leading=14, spaceAfter=6)
    heading = ParagraphStyle('SyntheticHeading', parent=body, fontSize=13, leading=17, spaceAfter=8)
    return colors, A4, body, heading


def render_lab_pdf(case, path, font):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    colors, a4, body, heading = pdf_tools(font)
    grid = TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTNAME', (0, 0), (-1, -1), 'Synthetic'),
                       ('FONTSIZE', (0, 0), (-1, -1), 9), ('VALIGN', (0, 0), (-1, -1), 'TOP')])

    small = ParagraphStyle('SyntheticCell', parent=body, fontSize=8, leading=10, spaceAfter=0)

    def table(panel, widths):
        style = small if case['id'] == 'lab-07' else body
        cells = [[Paragraph(c, style) for c in case['columns']]]
        cells += [[Paragraph(c, style) for c in row] for row in panel['rows']]
        result = Table(cells, colWidths=widths, repeatRows=1)
        result.setStyle(grid)
        return result

    story = [Paragraph(case['header'][0], heading)] + [Paragraph(line, body) for line in case['header'][1:]]
    story.append(Spacer(1, 10))
    if case['id'] == 'lab-07':
        halves = []
        for panel in case['panels']:
            halves.append([Paragraph(panel['caption'][0], body), table(panel, [72, 58, 62, 58])])
        outer = Table([halves], colWidths=[255, 255])
        outer.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story.append(outer)
    else:
        page = 1
        for panel in case['panels']:
            if panel['page'] != page:
                story.append(PageBreak())
                page = panel['page']
            story += [Paragraph(line, body) for line in panel.get('caption', [])]
            story += [table(panel, [170, 70, 70, 170]), Spacer(1, 12)]
    story.append(Paragraph('Комментарий: отклонение результата не является диагнозом.', body))

    def running(canvas, document):
        # lab-10: header/footer repeated on every page, as in real multi-page blanks.
        if case['id'] == 'lab-10':
            canvas.setFont('Synthetic', 8)
            canvas.drawString(40, a4[1] - 30, 'Синтетическая лаборатория «Образец-12» · синтетический бланк')
            canvas.drawString(40, 25, f'Страница {document.page} из 3')

    SimpleDocTemplate(str(path), pagesize=a4, title='Synthetic', author='Synthetic').build(
        story, onFirstPage=running, onLaterPages=running)


def render_visit_pdf(case, path, font):
    from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph
    _, a4, body, heading = pdf_tools(font)
    width, height = a4
    if case.get('columns') == 2:
        gap, margin = 20, 50
        column = (width - 2 * margin - gap) / 2
        frames = [Frame(margin, margin, column, height - 2 * margin, id='left'),
                  Frame(margin + column + gap, margin, column, height - 2 * margin, id='right')]
    else:
        frame_width = 230 if case.get('narrow') else width - 100
        frames = [Frame(50, 50, frame_width, height - 100, id='main')]
    document = BaseDocTemplate(str(path), pagesize=a4, title='Synthetic', author='Synthetic')
    document.addPageTemplates([PageTemplate(id='page', frames=frames)])
    story = []
    for index, page in enumerate(case['pages']):
        if index:
            story.append(PageBreak())
        for block in page:
            if block[0] == 'h':
                story.append(Paragraph(block[1], heading))
            elif block[0] == 'p':
                story.append(Paragraph(' '.join(sentence for sentence, _ in visit_items(block)), body))
    if case.get('columns') == 2:
        # Force the second column to be used: the reading order is the test, not the length.
        from reportlab.platypus import FrameBreak
        story.insert(3, FrameBreak())
    document.build(story)


# ---------------------------------------------------------------- review worksheet
def review_sheet(cases):
    lines = ['# Проверка эталонной разметки P0 — требуется человек', '',
             'Все документы синтетические. Эталон подготовлен AI по определениям в `scripts/generate_ingestion_p0.py`,'
             ' а не по выводу модели или парсера. Независимая проверка НЕ выполнена.', '',
             'Как проверять: откройте оригинал из `originals/` (PDF — в просмотрщике, не через извлечённый текст)'
             ' и сверьте каждую строку ниже с тем, что напечатано. Отмечайте `OK` или пишите исправление и основание.'
             ' Не выводите диагноз из медицинских знаний и не подгоняйте эталон под ответ модели. Исправления вносятся'
             ' новой версией набора (`ingestion-p0-v2`), исходная версия и причина сохраняются.', '',
             'Для LAB: название, результат со знаком, единица, референс как напечатан, даты по ролям'
             ' (SPECIMEN — взятие материала, RESULT — выдача результата, STUDY — дата исследования), субъект, страница.', '',
             'Для VISIT: субъект (PATIENT/FAMILY/OTHER/UNKNOWN), утверждение (CONFIRMED/SUSPECTED/NEGATED/'
             'NOT_CONFIRMED/RULED_OUT/UNKNOWN), лекарственное событие (PRESCRIBED/TAKING/NOT_STARTED/NOT_TAKING/'
             'STOPPED), время (CURRENT — на момент записи, HISTORICAL, FUTURE) и страница. Также проверьте, что'
             ' в документе нет заболеваний, симптомов или лекарств, пропущенных в эталоне.', '',
             'Проверяющий: ____ Дата: ____ Результат: НЕ ПРОВЕРЕНО', '']
    for case in cases:
        lines += [f"## {case['id']} ({case['split']}, {case['format'].upper()}, {case['layout']})",
                  f"Оригинал: `originals/{case['originalFile']}`", '']
        if case['type'] == 'LAB_REPORT':
            lines += ['| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |',
                      '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
            for n, r in enumerate(case['rows']):
                dates = ', '.join(f'{k} {v}' for k, v in r['dates'].items())
                lines.append(f"| {n} | {r['test']} | {r['result']} | {r['unit'] or '—'} | {r['reference'] or '—'} | "
                             f"{dates} | {r['subject']} | {r['page']} | ____ |")
        else:
            for n, s in enumerate(case['statements']):
                lines += [f"{n}. «{s['sourceText']}» (стр. {s['page']})",
                          f"   {s['name']} | {s['kind']} | {s['subject']} | {s['assertion']} | "
                          f"{s['medicationState']} | {s['temporality']} — решение: ____"]
        lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path, default=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                        help='Cyrillic-capable TTF used only for rendering synthetic PDFs')
    args = parser.parse_args()
    if ROOT.exists():
        raise SystemExit('Refusing to overwrite the frozen P0 set; create a new version instead.')
    if not args.font.is_file():
        raise SystemExit('Provide --font with a Cyrillic-capable TTF font.')
    originals, gold_dir = ROOT / 'originals', ROOT / 'gold'
    originals.mkdir(parents=True)
    gold_dir.mkdir()
    cases = []
    for case in LABS + VISITS:
        lab = case in LABS
        name = f"{case['id']}.{case['format']}"
        path = originals / name
        if case['format'] == 'pdf':
            (render_lab_pdf if lab else render_visit_pdf)(case, path, args.font)
        else:
            text = render_lab_text(case) if lab else render_visit_text(case)
            path.write_text(text, encoding='utf-8', newline='\n')
        entry = dict(id=case['id'], type='LAB_REPORT' if lab else 'VISIT', split=case['split'],
                     format=case['format'], layout=case['layout'], originalFile=name,
                     sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        entry['rows' if lab else 'statements'] = lab_gold(case) if lab else visit_gold(case)
        cases.append(entry)
    manifest = dict(
        version='ingestion-p0-v1', schemaVersion='p0-gold-v1', synthetic=True,
        goldReview='AI-authored from generator definitions; independent human review pending (gold/GOLD_REVIEW.md).',
        scope='24 fictional originals (12 LAB_REPORT, 12 VISIT) with layouts not used to tune lab-rows-v1 or '
              'clinical-v1. Held-out documents must not be used for tuning. Small correlated synthetic set.',
        cases=cases)
    (gold_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                            encoding='utf-8', newline='\n')
    (gold_dir / 'GOLD_REVIEW.md').write_text(review_sheet(cases), encoding='utf-8', newline='\n')
    rows = sum(len(c.get('rows', [])) for c in cases)
    statements = sum(len(c.get('statements', [])) for c in cases)
    held = sum(c['split'] == 'held-out' for c in cases)
    print(f'cases={len(cases)} labRows={rows} visitStatements={statements} heldOut={held}')


if __name__ == '__main__':
    main()
