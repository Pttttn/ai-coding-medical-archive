# Проверка эталонной разметки P0 — требуется человек

Все документы синтетические. Эталон подготовлен AI по определениям в `scripts/generate_ingestion_p0.py`, а не по выводу модели или парсера. Независимая проверка НЕ выполнена.

Как проверять: откройте оригинал из `originals/` (PDF — в просмотрщике, не через извлечённый текст) и сверьте каждую строку ниже с тем, что напечатано. Отмечайте `OK` или пишите исправление и основание. Не выводите диагноз из медицинских знаний и не подгоняйте эталон под ответ модели. Исправления вносятся новой версией набора (`ingestion-p0-v2`), исходная версия и причина сохраняются.

Для LAB: название, результат со знаком, единица, референс как напечатан, даты по ролям (SPECIMEN — взятие материала, RESULT — выдача результата, STUDY — дата исследования), субъект, страница.

Для VISIT: субъект (PATIENT/FAMILY/OTHER/UNKNOWN), утверждение (CONFIRMED/SUSPECTED/NEGATED/NOT_CONFIRMED/RULED_OUT/UNKNOWN), лекарственное событие (PRESCRIBED/TAKING/NOT_STARTED/NOT_TAKING/STOPPED), время (CURRENT — на момент записи, HISTORICAL, FUTURE) и страница. Также проверьте, что в документе нет заболеваний, симптомов или лекарств, пропущенных в эталоне.

Проверяющий: ____ Дата: ____ Результат: НЕ ПРОВЕРЕНО

## lab-01 (development, TXT, fixed-width columns without separators)
Оригинал: `originals/lab-01.txt`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Гемоглобин | 131 | г/л | 130–160 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |
| 1 | Эритроциты | 4,38 | 10^12/л | 4,0–5,0 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |
| 2 | Гематокрит | 39,5 | % | 40–48 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |
| 3 | Лейкоциты | 11,2 | 10^9/л | 4,0–9,0 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |
| 4 | Нейтрофилы сегментоядерные | 71 | % | 47–72 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |
| 5 | Лимфоциты | 18 | % | 19–37 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |
| 6 | Моноциты | 7 | % | 3–11 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |
| 7 | Эозинофилы | 3 | % | 0,5–5 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |
| 8 | Тромбоциты | 265 | 10^9/л | 180–320 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |
| 9 | СОЭ | 24 | мм/ч | 2–15 | SPECIMEN 2026-02-03, RESULT 2026-02-04 | PATIENT | 1 | ____ |

## lab-02 (development, MD, markdown table, five columns with flag)
Оригинал: `originals/lab-02.md`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Глюкоза | 6,4 | ммоль/л | 3,9–6,1 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 1 | Креатинин | 118 | мкмоль/л | 62–106 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 2 | СКФ (CKD-EPI) | >60 | мл/мин/1,73м² | >60 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 3 | Мочевая кислота | 452 | мкмоль/л | 202–416 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 4 | Общий белок | 71 | г/л | 64–83 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 5 | Альбумин | 44 | г/л | 35–52 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 6 | Билирубин общий | 9,8 | мкмоль/л | 3,4–20,5 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 7 | АЛТ | <7 | Ед/л | <41 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 8 | АСТ | 19 | Ед/л | <40 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 9 | Щелочная фосфатаза | 87 | Ед/л | 40–129 | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |
| 10 | Амилаза | 58 | Ед/л | — | SPECIMEN 2026-02-10, RESULT 2026-02-11 | PATIENT | 1 | ____ |

## lab-03 (development, PDF, PDF grid table over two pages, letterhead, wrapped cells)
Оригинал: `originals/lab-03.pdf`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Холестерин общий | 5,9 | ммоль/л | <5,2 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 1 | ____ |
| 1 | Холестерин липопротеинов высокой плотности | 1,02 | ммоль/л | >1,0 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 1 | ____ |
| 2 | Холестерин липопротеинов низкой плотности | 3,84 | ммоль/л | желательно <3,0; погранично 3,0–4,1 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 1 | ____ |
| 3 | Триглицериды | 1,9 | ммоль/л | <1,7 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 1 | ____ |
| 4 | Аполипопротеин A1 | 1,31 | г/л | 1,05–2,05 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 1 | ____ |
| 5 | Аполипопротеин B | 1,12 | г/л | 0,6–1,17 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 1 | ____ |
| 6 | Липопротеин (а) | 74 | нмоль/л | <75 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 1 | ____ |
| 7 | Гомоцистеин | 13,8 | мкмоль/л | 5–15 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 2 | ____ |
| 8 | hs-СРБ | 3,4 | мг/л | <1,0 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 2 | ____ |
| 9 | Ферритин | 96 | мкг/л | 30–400 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 2 | ____ |
| 10 | Витамин D (25-OH) | 21,5 | нг/мл | 30–100 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 2 | ____ |
| 11 | NT-proBNP | 88 | пг/мл | <125 | SPECIMEN 2026-03-05, RESULT 2026-03-06 | PATIENT | 2 | ____ |

## lab-04 (development, TXT, dash list with unit and parenthesised reference)
Оригинал: `originals/lab-04.txt`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Глюкоза | 99 | мг/дл | 70–99 | STUDY 2026-03-12 | PATIENT | 1 | ____ |
| 1 | Холестерин общий | 212 | мг/дл | <200 | STUDY 2026-03-12 | PATIENT | 1 | ____ |
| 2 | Холестерин ЛПНП | 138 | мг/дл | <130 | STUDY 2026-03-12 | PATIENT | 1 | ____ |
| 3 | Холестерин ЛПВП | 47 | мг/дл | >40 | STUDY 2026-03-12 | PATIENT | 1 | ____ |
| 4 | Триглицериды | 135 | мг/дл | <150 | STUDY 2026-03-12 | PATIENT | 1 | ____ |
| 5 | Креатинин | 1,05 | мг/дл | 0,7–1,2 | STUDY 2026-03-12 | PATIENT | 1 | ____ |
| 6 | Мочевина | 31 | мг/дл | 17–43 | STUDY 2026-03-12 | PATIENT | 1 | ____ |
| 7 | Кальций общий | 9,6 | мг/дл | 8,6–10,3 | STUDY 2026-03-12 | PATIENT | 1 | ____ |
| 8 | Калий | 4,4 | ммоль/л | 3,5–5,1 | STUDY 2026-03-12 | PATIENT | 1 | ____ |
| 9 | Инсулин | 14,2 | мкЕд/мл | — | STUDY 2026-03-12 | PATIENT | 1 | ____ |

## lab-05 (development, PDF, PDF, two panels with different specimen dates, repeated tests)
Оригинал: `originals/lab-05.pdf`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Железо сывороточное | 7,4 | мкмоль/л | 10,7–32,2 | SPECIMEN 2026-04-01, RESULT 2026-04-02 | PATIENT | 1 | ____ |
| 1 | ОЖСС | 78 | мкмоль/л | 45–77 | SPECIMEN 2026-04-01, RESULT 2026-04-02 | PATIENT | 1 | ____ |
| 2 | Ферритин | 9 | мкг/л | 15–150 | SPECIMEN 2026-04-01, RESULT 2026-04-02 | PATIENT | 1 | ____ |
| 3 | Трансферрин | 3,9 | г/л | 2,0–3,6 | SPECIMEN 2026-04-01, RESULT 2026-04-02 | PATIENT | 1 | ____ |
| 4 | Витамин B12 | 162 | пг/мл | 187–883 | SPECIMEN 2026-04-01, RESULT 2026-04-02 | PATIENT | 1 | ____ |
| 5 | Железо сывороточное | 9,1 | мкмоль/л | 10,7–32,2 | SPECIMEN 2026-04-08, RESULT 2026-04-09 | PATIENT | 1 | ____ |
| 6 | Ферритин | 11 | мкг/л | 15–150 | SPECIMEN 2026-04-08, RESULT 2026-04-09 | PATIENT | 1 | ____ |
| 7 | Гемоглобин | 112 | г/л | 120–140 | SPECIMEN 2026-04-08, RESULT 2026-04-09 | PATIENT | 1 | ____ |
| 8 | Ретикулоциты | 2,4 | % | 0,5–1,5 | SPECIMEN 2026-04-08, RESULT 2026-04-09 | PATIENT | 1 | ____ |
| 9 | Фолиевая кислота | >20 | нг/мл | 3,1–20,5 | SPECIMEN 2026-04-08, RESULT 2026-04-09 | PATIENT | 1 | ____ |

## lab-06 (development, TXT, pipe table, results of a family member)
Оригинал: `originals/lab-06.txt`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | ТТГ | 6,8 | мМЕ/л | 0,4–4,0 | RESULT 2026-01-20 | FAMILY | 1 | ____ |
| 1 | Свободный Т4 | 10,1 | пмоль/л | 9–19 | RESULT 2026-01-20 | FAMILY | 1 | ____ |
| 2 | АТ-ТПО | >1000 | МЕ/мл | <34 | RESULT 2026-01-20 | FAMILY | 1 | ____ |
| 3 | АТ к рецептору ТТГ | <0,8 | МЕ/л | <1,75 | RESULT 2026-01-20 | FAMILY | 1 | ____ |
| 4 | Тиреоглобулин | 3,2 | нг/мл | 3,5–77 | RESULT 2026-01-20 | FAMILY | 1 | ____ |
| 5 | Кальцитонин | <2 | пг/мл | <6,4 | RESULT 2026-01-20 | FAMILY | 1 | ____ |
| 6 | Пролактин | 312 | мМЕ/л | 102–496 | RESULT 2026-01-20 | FAMILY | 1 | ____ |
| 7 | Кортизол | 455 | нмоль/л | 171–536 | RESULT 2026-01-20 | FAMILY | 1 | ____ |
| 8 | Антитела к тиреоглобулину | отрицательно | — | — | RESULT 2026-01-20 | FAMILY | 1 | ____ |
| 9 | Паратгормон | 5,1 | пмоль/л | — | RESULT 2026-01-20 | FAMILY | 1 | ____ |

## lab-07 (held-out, PDF, PDF, two tables side by side on one page)
Оригинал: `originals/lab-07.pdf`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Удельный вес | 1,028 | — | 1,010–1,025 | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |
| 1 | pH | 5,5 | — | 5,0–7,0 | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |
| 2 | Белок | 0,3 | г/л | <0,14 | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |
| 3 | Глюкоза | не обнаружено | — | не обнаружено | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |
| 4 | Лейкоциты | 3 | в п/з | 0–5 | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |
| 5 | Альбумин/креатинин | 4,1 | мг/ммоль | <3,0 | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |
| 6 | Креатинин мочи | 12,4 | ммоль/л | — | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |
| 7 | Натрий мочи | 146 | ммоль/сут | 40–220 | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |
| 8 | Калий мочи | 58 | ммоль/сут | 25–125 | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |
| 9 | Кальций мочи | 6,8 | ммоль/сут | 2,5–7,5 | SPECIMEN 2026-05-14, RESULT 2026-05-15 | PATIENT | 1 | ____ |

## lab-08 (held-out, MD, English markdown table with different headers)
Оригинал: `originals/lab-08.md`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Hemoglobin A1c | 7.2 | % | 4.0–5.6 | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |
| 1 | Fasting glucose | 8.1 | mmol/L | 3.9–5.5 | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |
| 2 | C-peptide | 0.42 | nmol/L | 0.37–1.47 | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |
| 3 | Microalbumin | >150 | mg/L | <20 | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |
| 4 | eGFR | 74 | mL/min/1.73m² | >90 | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |
| 5 | Cystatin C | 1.09 | mg/L | 0.61–0.95 | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |
| 6 | GAD antibodies | negative | — | — | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |
| 7 | Ketones (urine) | negative | — | negative | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |
| 8 | Lactate | 1.6 | mmol/L | 0.5–2.2 | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |
| 9 | Uric acid | 6.9 | mg/dL | 3.5–7.2 | SPECIMEN 2026-06-03, RESULT 2026-06-04 | PATIENT | 1 | ____ |

## lab-09 (held-out, TXT, pipe table with wrapped test names and page break)
Оригинал: `originals/lab-09.txt`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Холестерин липопротеинов низкой плотности | 4,6 | ммоль/л | <3,0 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 1 | Холестерин общий | 6,8 | ммоль/л | <5,2 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 2 | Триглицериды | 2,9 | ммоль/л | <1,7 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 3 | Коэффициент атерогенности | 4,1 | — | <3,0 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 4 | Глюкоза | 5,8 | ммоль/л | 4,1–5,9 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 5 | Гликированный гемоглобин | 6,1 | % | <6,0 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 6 | Аланинаминотрансфераза (АЛТ) | 62 | Ед/л | <41 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 7 | Аспартатаминотрансфераза (АСТ) | 44 | Ед/л | <40 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 8 | Гамма-глутамилтрансфераза | 97 | Ед/л | 10–71 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 9 | Билирубин прямой | 4,1 | мкмоль/л | <5,0 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |
| 10 | Щелочная фосфатаза | 101 | Ед/л | 40–129 | SPECIMEN 2026-06-21, RESULT 2026-06-22 | PATIENT | 1 | ____ |

## lab-10 (held-out, PDF, PDF over three pages, running header/footer, other column names)
Оригинал: `originals/lab-10.pdf`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | ТТГ | 2,31 | мкМЕ/мл | 0,4–4,0 | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 1 | ____ |
| 1 | Т4 свободный | 14,6 | пмоль/л | 9–19 | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 1 | ____ |
| 2 | Т3 свободный | 4,9 | пмоль/л | 2,6–5,7 | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 1 | ____ |
| 3 | Антитела к ТПО | <5 | МЕ/мл | <34 | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 1 | ____ |
| 4 | Эстрадиол | 412 | пмоль/л | зависит от фазы цикла | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 2 | ____ |
| 5 | ЛГ | 7,8 | мМЕ/мл | 2,4–12,6 | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 2 | ____ |
| 6 | ФСГ | 6,1 | мМЕ/мл | 3,5–12,5 | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 2 | ____ |
| 7 | Прогестерон | 1,2 | нмоль/л | — | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 2 | ____ |
| 8 | Витамин B12 | 518 | пг/мл | 187–883 | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 3 | ____ |
| 9 | Витамин D (25-OH) | 38,4 | нг/мл | 30–100 | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 3 | ____ |
| 10 | Цинк | 11,9 | мкмоль/л | 10,7–18,4 | SPECIMEN 2026-07-02, RESULT 2026-07-03 | PATIENT | 3 | ____ |

## lab-11 (held-out, TXT, labelled lines with ×10⁹ units, thousands separator, flags)
Оригинал: `originals/lab-11.txt`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Лейкоциты | 5,6 | ×10⁹/л | 4,0–9,0 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 1 | Нейтрофилы абс. | 3,4 | ×10⁹/л | 1,8–7,7 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 2 | D-димер | 1 250 | нг/мл FEU | <500 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 3 | Прокальцитонин | <0,05 | нг/мл | <0,5 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 4 | СРБ | 12,6 | мг/л | 0–5 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 5 | Фибриноген | 4,1 | г/л | 2,0–4,0 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 6 | МНО | 1,12 | — | 0,85–1,15 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 7 | Лактатдегидрогеназа | 245 | Ед/л | 135–225 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 8 | Ферритин | 380 | мкг/л | 30–400 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 9 | Интерлейкин-6 | 4,2 | пг/мл | не установлен | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |
| 10 | Тропонин T высокочувствительный | 9 | нг/л | <14 | SPECIMEN 2026-08-10, RESULT 2026-08-11 | PATIENT | 1 | ____ |

## lab-12 (held-out, MD, markdown bullets, no subject, specimen date only)
Оригинал: `originals/lab-12.md`

| # | Показатель | Результат | Единица | Референс | Даты | Субъект | Стр. | Решение |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Ферритин | 12 | мкг/л | 15–150 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 1 | Железо | 8,2 | мкмоль/л | 9–30,4 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 2 | Трансферрин | 3,7 | г/л | 2,0–3,6 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 3 | Насыщение трансферрина железом | 11 | % | 20–50 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 4 | Витамин B12 | 205 | пг/мл | 187–883 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 5 | Фолиевая кислота | 4,3 | нг/мл | 3,1–20,5 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 6 | Гемоглобин | 109 | г/л | 120–140 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 7 | MCV | 76 | фл | 80–100 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 8 | MCH | 24,1 | пг | 27–31 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 9 | RDW-CV | 16,8 | % | 11,5–14,5 | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |
| 10 | Гепсидин | 3,1 | нг/мл | — | SPECIMEN 2026-09-01 | UNKNOWN | 1 | ____ |

## visit-01 (development, TXT, prose sections, two dates, doses)
Оригинал: `originals/visit-01.txt`

0. «Пациент жалуется на изжогу после еды в течение трёх недель.» (стр. 1)
   изжогу | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Боли за грудиной при нагрузке пациент отрицает.» (стр. 1)
   Боли за грудиной | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «В 2021 году у пациента диагностирована язвенная болезнь двенадцатиперстной кишки.» (стр. 1)
   язвенная болезнь двенадцатиперстной кишки | CONDITION | PATIENT | CONFIRMED | NOT_APPLICABLE | HISTORICAL — решение: ____
3. «У матери пациента рак желудка выявлен в 58 лет.» (стр. 1)
   рак желудка | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | HISTORICAL — решение: ____
4. «Предварительно: гастроэзофагеальная рефлюксная болезнь, требуется подтверждение после ФГДС.» (стр. 1)
   гастроэзофагеальная рефлюксная болезнь | CONDITION | PATIENT | SUSPECTED | NOT_APPLICABLE | CURRENT — решение: ____
5. «Назначен омепразол 20 мг 2 раза в день за 30 минут до еды на 4 недели.» (стр. 1)
   омепразол | MEDICATION | PATIENT | UNKNOWN | PRESCRIBED | CURRENT — решение: ____
6. «Ранее принимавшийся ибупрофен 400 мг отменён.» (стр. 1)
   ибупрофен | MEDICATION | PATIENT | UNKNOWN | STOPPED | CURRENT — решение: ____

## visit-02 (development, MD, markdown headings and bullets)
Оригинал: `originals/visit-02.md`

0. «Периодическое сердцебиение по вечерам.» (стр. 1)
   сердцебиение | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Одышка при нагрузке не беспокоит.» (стр. 1)
   Одышка | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Гипертоническая болезнь с 2018 года, наблюдается постоянно.» (стр. 1)
   Гипертоническая болезнь | CONDITION | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
3. «У отца инфаркт миокарда в 52 года.» (стр. 1)
   инфаркт миокарда | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | HISTORICAL — решение: ____
4. «У брата пациента фибрилляция предсердий не подтверждена.» (стр. 1)
   фибрилляция предсердий | CONDITION | FAMILY | NOT_CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
5. «Бисопролол 2,5 мг утром принимает регулярно, продолжить.» (стр. 1)
   Бисопролол | MEDICATION | PATIENT | UNKNOWN | TAKING | CURRENT — решение: ____
6. «Аторвастатин 20 мг назначен, пациент пока не начал приём.» (стр. 1)
   Аторвастатин | MEDICATION | PATIENT | UNKNOWN | NOT_STARTED | CURRENT — решение: ____
7. «Пароксизмальная тахикардия предполагается, назначено суточное мониторирование ЭКГ.» (стр. 1)
   Пароксизмальная тахикардия | CONDITION | PATIENT | SUSPECTED | NOT_APPLICABLE | CURRENT — решение: ____

## visit-03 (development, PDF, PDF over two pages)
Оригинал: `originals/visit-03.pdf`

0. «Пациент отмечает головные боли давящего характера 2–3 раза в неделю.» (стр. 1)
   головные боли | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Тошнота на высоте головной боли отсутствует.» (стр. 1)
   Тошнота | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Онемение в левой руке было в ноябре 2025 года, сейчас не повторяется.» (стр. 1)
   Онемение в левой руке | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | HISTORICAL — решение: ____
3. «У сестры пациента мигрень с аурой подтверждена неврологом.» (стр. 1)
   мигрень с аурой | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
4. «Мигрень без ауры у пациента не исключена, но критериев недостаточно.» (стр. 2)
   Мигрень без ауры | CONDITION | PATIENT | SUSPECTED | NOT_APPLICABLE | CURRENT — решение: ____
5. «Рассеянный склероз по данным МРТ исключён.» (стр. 2)
   Рассеянный склероз | CONDITION | PATIENT | RULED_OUT | NOT_APPLICABLE | CURRENT — решение: ____
6. «Амитриптилин 10 мг на ночь назначен с понедельника.» (стр. 2)
   Амитриптилин | MEDICATION | PATIENT | UNKNOWN | PRESCRIBED | FUTURE — решение: ____
7. «Суматриптан 50 мг пациент принимал в 2024 году, прекратил из-за побочных эффектов.» (стр. 2)
   Суматриптан | MEDICATION | PATIENT | UNKNOWN | STOPPED | HISTORICAL — решение: ____

## visit-04 (development, TXT, hard-wrapped lines inside sentences)
Оригинал: `originals/visit-04.txt`

0. «Сахарный диабет 2 типа диагностирован в 2019 году и остаётся под наблюдением.» (стр. 1)
   Сахарный диабет 2 типа | CONDITION | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Жажда и учащённое мочеиспускание в последний месяц не отмечаются.» (стр. 1)
   Жажда | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Жажда и учащённое мочеиспускание в последний месяц не отмечаются.» (стр. 1)
   учащённое мочеиспускание | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
3. «Диабетическая ретинопатия не подтверждена при осмотре окулиста.» (стр. 1)
   Диабетическая ретинопатия | CONDITION | PATIENT | NOT_CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
4. «Пациент принимает метформин 1000 мг 2 раза в день.» (стр. 1)
   метформин | MEDICATION | PATIENT | UNKNOWN | TAKING | CURRENT — решение: ____
5. «Эмпаглифлозин 10 мг был назначен в марте и отменён через две недели.» (стр. 1)
   Эмпаглифлозин | MEDICATION | PATIENT | UNKNOWN | STOPPED | HISTORICAL — решение: ____
6. «У матери пациента сахарный диабет 2 типа.» (стр. 1)
   сахарный диабет 2 типа | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____

## visit-05 (development, TXT, telephone note without a visit heading)
Оригинал: `originals/visit-05.txt`

0. «Пациент сообщает, что кашель прошёл неделю назад.» (стр. 1)
   кашель | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | HISTORICAL — решение: ____
1. «Лихорадка отсутствует.» (стр. 1)
   Лихорадка | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Амоксициллин 500 мг пациент допил полностью, курс завершён.» (стр. 1)
   Амоксициллин | MEDICATION | PATIENT | UNKNOWN | STOPPED | HISTORICAL — решение: ____
3. «Пневмония по контрольному снимку исключена.» (стр. 1)
   Пневмония | CONDITION | PATIENT | RULED_OUT | NOT_APPLICABLE | CURRENT — решение: ____
4. «Ацетилцистеин рекомендован, но пациент его не начинал.» (стр. 1)
   Ацетилцистеин | MEDICATION | PATIENT | UNKNOWN | NOT_STARTED | CURRENT — решение: ____
5. «У супруги пациента сейчас бронхит.» (стр. 1)
   бронхит | CONDITION | OTHER | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____

## visit-06 (development, MD, markdown bullets, biopsy date)
Оригинал: `originals/visit-06.md`

0. «Атопический дерматит был в детстве.» (стр. 1)
   Атопический дерматит | CONDITION | PATIENT | CONFIRMED | NOT_APPLICABLE | HISTORICAL — решение: ____
1. «Зуд беспокоит по ночам.» (стр. 1)
   Зуд | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Псориаз у пациента подозревается, ждём гистологию.» (стр. 1)
   Псориаз | CONDITION | PATIENT | SUSPECTED | NOT_APPLICABLE | CURRENT — решение: ____
3. «Микоз стоп по посеву не подтверждён.» (стр. 1)
   Микоз стоп | CONDITION | PATIENT | NOT_CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
4. «У дочери пациента псориаз подтверждён.» (стр. 1)
   псориаз | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
5. «Мометазон крем 0,1% 1 раз в день на 14 дней назначен.» (стр. 1)
   Мометазон | MEDICATION | PATIENT | UNKNOWN | PRESCRIBED | CURRENT — решение: ____
6. «Цетиризин 10 мг пациент принимает сам последние две недели.» (стр. 1)
   Цетиризин | MEDICATION | PATIENT | UNKNOWN | TAKING | CURRENT — решение: ____

## visit-07 (held-out, PDF, PDF with two text columns)
Оригинал: `originals/visit-07.pdf`

0. «Пациент жалуется на вздутие живота после молочных продуктов.» (стр. 1)
   вздутие живота | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Кровь в стуле пациент отрицает.» (стр. 1)
   Кровь в стуле | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Целиакия по данным серологии исключена.» (стр. 1)
   Целиакия | CONDITION | PATIENT | RULED_OUT | NOT_APPLICABLE | CURRENT — решение: ____
3. «Лактазная недостаточность предполагается.» (стр. 1)
   Лактазная недостаточность | CONDITION | PATIENT | SUSPECTED | NOT_APPLICABLE | CURRENT — решение: ____
4. «У отца пациента болезнь Крона.» (стр. 1)
   болезнь Крона | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
5. «Мебеверин 200 мг 2 раза в день назначен на 4 недели.» (стр. 1)
   Мебеверин | MEDICATION | PATIENT | UNKNOWN | PRESCRIBED | CURRENT — решение: ____
6. «Пантопразол пациент перестал принимать в мае.» (стр. 1)
   Пантопразол | MEDICATION | PATIENT | UNKNOWN | STOPPED | HISTORICAL — решение: ____

## visit-08 (held-out, MD, English clinical note)
Оригинал: `originals/visit-08.md`

0. «The patient reports intermittent palpitations.» (стр. 1)
   palpitations | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Chest pain is denied.» (стр. 1)
   Chest pain | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Atrial fibrillation was ruled out on Holter monitoring.» (стр. 1)
   Atrial fibrillation | CONDITION | PATIENT | RULED_OUT | NOT_APPLICABLE | CURRENT — решение: ____
3. «Hypothyroidism is suspected; TSH is pending.» (стр. 1)
   Hypothyroidism | CONDITION | PATIENT | SUSPECTED | NOT_APPLICABLE | CURRENT — решение: ____
4. «The patient's mother has atrial fibrillation.» (стр. 1)
   atrial fibrillation | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
5. «Metoprolol 25 mg was prescribed but not started.» (стр. 1)
   Metoprolol | MEDICATION | PATIENT | UNKNOWN | NOT_STARTED | CURRENT — решение: ____
6. «Aspirin 75 mg was discontinued last year.» (стр. 1)
   Aspirin | MEDICATION | PATIENT | UNKNOWN | STOPPED | HISTORICAL — решение: ____

## visit-09 (held-out, TXT, outpatient extract, period and extract date)
Оригинал: `originals/visit-09.txt`

0. «Бронхиальная астма установлена в 2015 году, в настоящее время контролируемая.» (стр. 1)
   Бронхиальная астма | CONDITION | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Приступы удушья за последний год не отмечались.» (стр. 1)
   Приступы удушья | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Аллергический ринит у пациента предполагается по сезонности симптомов.» (стр. 1)
   Аллергический ринит | CONDITION | PATIENT | SUSPECTED | NOT_APPLICABLE | CURRENT — решение: ____
3. «У бабушки пациента по материнской линии была бронхиальная астма.» (стр. 1)
   бронхиальная астма | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | HISTORICAL — решение: ____
4. «Будесонид/формотерол 160/4,5 мкг по 1 вдоху 2 раза в день пациент получает постоянно.» (стр. 1)
   Будесонид/формотерол | MEDICATION | PATIENT | UNKNOWN | TAKING | CURRENT — решение: ____
5. «Монтелукаст 10 мг отменён в марте 2026 года.» (стр. 1)
   Монтелукаст | MEDICATION | PATIENT | UNKNOWN | STOPPED | HISTORICAL — решение: ____
6. «Сальбутамол по потребности назначен, пациент не использовал ни разу.» (стр. 1)
   Сальбутамол | MEDICATION | PATIENT | UNKNOWN | NOT_STARTED | CURRENT — решение: ____

## visit-10 (held-out, PDF, PDF, narrow column over two pages)
Оригинал: `originals/visit-10.pdf`

0. «Боли в мелких суставах кистей беспокоят около двух месяцев.» (стр. 1)
   Боли в мелких суставах кистей | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Утренняя скованность отсутствует.» (стр. 1)
   Утренняя скованность | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Ревматоидный артрит пока не подтверждён, ожидаются результаты АЦЦП.» (стр. 1)
   Ревматоидный артрит | CONDITION | PATIENT | NOT_CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
3. «Подагра у пациента исключена.» (стр. 1)
   Подагра | CONDITION | PATIENT | RULED_OUT | NOT_APPLICABLE | CURRENT — решение: ____
4. «У тёти пациента системная красная волчанка.» (стр. 2)
   системная красная волчанка | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
5. «Нимесулид 100 мг пациент принимал до июля, сейчас не принимает.» (стр. 2)
   Нимесулид | MEDICATION | PATIENT | UNKNOWN | STOPPED | HISTORICAL — решение: ____
6. «Гидроксихлорохин 200 мг назначен с 15.08.2026.» (стр. 2)
   Гидроксихлорохин | MEDICATION | PATIENT | UNKNOWN | PRESCRIBED | FUTURE — решение: ____

## visit-11 (held-out, TXT, patient diary in first person, no visit heading)
Оригинал: `originals/visit-11.txt`

0. «Бессонница сохраняется почти каждую ночь.» (стр. 1)
   Бессонница | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Тревожность стала меньше.» (стр. 1)
   Тревожность | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Мелатонин 3 мг принимаю на ночь с 2 сентября.» (стр. 1)
   Мелатонин | MEDICATION | PATIENT | UNKNOWN | TAKING | CURRENT — решение: ____
3. «Золпидем врач выписал, но я его не начинал.» (стр. 1)
   Золпидем | MEDICATION | PATIENT | UNKNOWN | NOT_STARTED | CURRENT — решение: ____
4. «У мамы давно депрессия, она лечится.» (стр. 1)
   депрессия | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
5. «Панические атаки на этой неделе не повторялись.» (стр. 1)
   Панические атаки | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____

## visit-12 (held-out, MD, markdown bullets and a medication table)
Оригинал: `originals/visit-12.md`

0. «Учащённое ночное мочеиспускание до 3 раз за ночь.» (стр. 1)
   Учащённое ночное мочеиспускание | SYMPTOM | PATIENT | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
1. «Боли при мочеиспускании нет.» (стр. 1)
   Боли при мочеиспускании | SYMPTOM | PATIENT | NEGATED | NOT_APPLICABLE | CURRENT — решение: ____
2. «Мочекаменная болезнь в 2022 году, камень отошёл самостоятельно.» (стр. 1)
   Мочекаменная болезнь | CONDITION | PATIENT | CONFIRMED | NOT_APPLICABLE | HISTORICAL — решение: ____
3. «Доброкачественная гиперплазия предстательной железы предполагается по УЗИ.» (стр. 1)
   Доброкачественная гиперплазия предстательной железы | CONDITION | PATIENT | SUSPECTED | NOT_APPLICABLE | CURRENT — решение: ____
4. «У отца пациента рак предстательной железы.» (стр. 1)
   рак предстательной железы | CONDITION | FAMILY | CONFIRMED | NOT_APPLICABLE | CURRENT — решение: ____
5. «| Тамсулозин | 0,4 мг на ночь | принимает |» (стр. 1)
   Тамсулозин | MEDICATION | PATIENT | UNKNOWN | TAKING | CURRENT — решение: ____
6. «| Финастерид | 5 мг утром | назначен, не начат |» (стр. 1)
   Финастерид | MEDICATION | PATIENT | UNKNOWN | NOT_STARTED | CURRENT — решение: ____
7. «| Доксазозин | 2 мг | отменён в 2026-08 |» (стр. 1)
   Доксазозин | MEDICATION | PATIENT | UNKNOWN | STOPPED | HISTORICAL — решение: ____
