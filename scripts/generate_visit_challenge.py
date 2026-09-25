"""Additional synthetic challenge set; refuses to overwrite frozen originals/gold."""

import hashlib
import json
import re
from pathlib import Path

# Exact source spelling. One annotation per explicitly described event; no medical inference.
CASES = [
    (
        "d01",
        "development",
        "Терапевт / жалобы и план",
        "paired",
        [
            (
                "двоение",
                "SYMPTOM",
                "PATIENT",
                "NEGATED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Пациент уточняет: двоение отсутствует даже при чтении.",
            ),
            (
                "головокружение",
                "SYMPTOM",
                "PATIENT",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "При этом головокружение у пациента сохраняется.",
            ),
            (
                "диабет",
                "CONDITION",
                "FAMILY",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "У отца пациента диабет подтверждён и остаётся актуальным диагнозом.",
            ),
            (
                "диабет",
                "CONDITION",
                "PATIENT",
                "NOT_CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "У самого пациента диабет пока не подтверждён; обследование не закончено.",
            ),
            (
                "Амлодипин",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "PRESCRIBED",
                "FUTURE",
                "План: Амлодипин назначен пациенту со следующего вторника, сведений о фактическом старте нет.",
            ),
            (
                "Метформин",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "NOT_STARTED",
                "CURRENT",
                "Метформин пациенту выписали месяц назад, но он так и не принял ни одной таблетки.",
            ),
        ],
    ),
    (
        "d02",
        "development",
        "Сверка принадлежности записей",
        "lines",
        [
            (
                "Варфарин",
                "MEDICATION",
                "OTHER",
                "UNKNOWN",
                "TAKING",
                "CURRENT",
                "Варфарин принимает супруга; пациент рассказывает о её текущем лечении.",
            ),
            (
                "Бисопролол",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "NOT_TAKING",
                "CURRENT",
                "Бисопролол пациент сейчас не принимает; принимал ли когда-либо, установить не удалось.",
            ),
            (
                "аритмия",
                "CONDITION",
                "PATIENT",
                "RULED_OUT",
                "NOT_APPLICABLE",
                "CURRENT",
                "После обследования аритмия у пациента исключена.",
            ),
            (
                "астма",
                "CONDITION",
                "UNKNOWN",
                "UNKNOWN",
                "NOT_APPLICABLE",
                "UNKNOWN",
                "На листке написано только «астма»; принадлежность листка и статус диагноза неизвестны.",
            ),
            (
                "кашель",
                "SYMPTOM",
                "PATIENT",
                "NEGATED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Кашель? Ответ пациента на приёме: нет, кашель не беспокоит.",
            ),
            (
                "гипертония",
                "CONDITION",
                "FAMILY",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "У родной сестры пациента подтверждена гипертония, она продолжает наблюдаться.",
            ),
        ],
    ),
    (
        "d03",
        "development",
        "Хронология двух курсов",
        "paragraphs",
        [
            (
                "Ибупрофен",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "STOPPED",
                "HISTORICAL",
                "Первый курс: Ибупрофен пациент завершил в феврале 2025 года.",
            ),
            (
                "Ибупрофен",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "TAKING",
                "CURRENT",
                "Новый курс: Ибупрофен пациент фактически принимает сейчас по согласованной схеме.",
            ),
            (
                "перелом",
                "CONDITION",
                "PATIENT",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "HISTORICAL",
                "В 2019 году у пациента был подтверждён перелом лучевой кости.",
            ),
            (
                "артрит",
                "CONDITION",
                "PATIENT",
                "SUSPECTED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Текущее предположение врача для пациента — артрит, диагноз ещё проверяется.",
            ),
            (
                "отёк",
                "SYMPTOM",
                "PATIENT",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Сегодня при осмотре пациента сохраняется отёк кисти.",
            ),
            (
                "подагра",
                "CONDITION",
                "PATIENT",
                "NOT_CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Подозревавшаяся у пациента подагра не подтверждена, исключить её пока тоже нельзя.",
            ),
        ],
    ),
    (
        "d04",
        "development",
        "Беседа с неврологом",
        "paired",
        [
            (
                "тошнота",
                "SYMPTOM",
                "PATIENT",
                "NEGATED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Врач: беспокоит ли тошнота сейчас? Пациент: нет, тошнота отсутствует.",
            ),
            (
                "головная боль",
                "SYMPTOM",
                "PATIENT",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Врач: а головная боль? Пациент: да, сейчас есть головная боль.",
            ),
            (
                "инсульт",
                "CONDITION",
                "FAMILY",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "HISTORICAL",
                "Мать пациента перенесла подтверждённый инсульт в 2017 году.",
            ),
            (
                "инсульт",
                "CONDITION",
                "PATIENT",
                "RULED_OUT",
                "NOT_APPLICABLE",
                "CURRENT",
                "У пациента острый инсульт по результатам обследования исключён.",
            ),
            (
                "Напроксен",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
                "Напроксен указан в карточке пациента без сведений о назначении, приёме или отмене.",
            ),
            (
                "Парацетамол",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "PRESCRIBED",
                "FUTURE",
                "Врач назначил пациенту Парацетамол на завтра; факт приёма не установлен.",
            ),
        ],
    ),
    (
        "d05",
        "development",
        "Лекарственная сверка гастроэнтеролога",
        "lines",
        [
            (
                "Омепразол",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "TAKING",
                "CURRENT",
                "Омепразол: пациент подтвердил, что принимает его ежедневно в настоящее время.",
            ),
            (
                "Фамотидин",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "NOT_STARTED",
                "CURRENT",
                "Фамотидин: рецепт был выдан, но пациент сообщает, что лечение им вообще не начинал.",
            ),
            (
                "панкреатит",
                "CONDITION",
                "PATIENT",
                "NEGATED",
                "NOT_APPLICABLE",
                "HISTORICAL",
                "Панкреатит в прошлом пациент отрицает.",
            ),
            (
                "язва",
                "CONDITION",
                "PATIENT",
                "SUSPECTED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Предположение для пациента на текущем приёме: язва; подтверждающих результатов пока нет.",
            ),
            (
                "цирроз",
                "CONDITION",
                "OTHER",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "У соседа пациента имеется подтверждённый цирроз; это сведения исключительно о соседе.",
            ),
            (
                "рвота",
                "SYMPTOM",
                "PATIENT",
                "NEGATED",
                "NOT_APPLICABLE",
                "CURRENT",
                "По словам пациента, рвота отсутствует.",
            ),
        ],
    ),
    (
        "d06",
        "development",
        "Осмотр пульмонолога / уточнение статусов",
        "paragraphs",
        [
            (
                "бронхит",
                "CONDITION",
                "PATIENT",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Подтверждённый текущий диагноз пациента: бронхит.",
            ),
            (
                "пневмония",
                "CONDITION",
                "PATIENT",
                "NOT_CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "У пациента пневмония не подтверждена, но обследование ещё продолжается.",
            ),
            (
                "туберкулёз",
                "CONDITION",
                "PATIENT",
                "RULED_OUT",
                "NOT_APPLICABLE",
                "CURRENT",
                "У пациента туберкулёз окончательно исключён врачом.",
            ),
            (
                "Преднизолон",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "STOPPED",
                "HISTORICAL",
                "Преднизолон пациенту отменили пять дней назад, он прекратил курс.",
            ),
            (
                "Сальбутамол",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
                "Сальбутамол упомянут в списке пациента; установить, назначен ли он и используется ли, не удалось.",
            ),
            (
                "одышка",
                "SYMPTOM",
                "PATIENT",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "На сегодняшнем приёме пациент жалуется на одышку при обычной ходьбе.",
            ),
        ],
    ),
    (
        "h01",
        "held-out",
        "Протокол уточняющей офтальмологической беседы",
        "paired",
        [
            (
                "светобоязнь",
                "SYMPTOM",
                "PATIENT",
                "NEGATED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Со слов пациента на сегодняшний день светобоязнь полностью отсутствует.",
            ),
            (
                "слезотечение",
                "SYMPTOM",
                "PATIENT",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "В отличие от этого, слезотечение пациента сегодня беспокоит.",
            ),
            (
                "увеит",
                "CONDITION",
                "PATIENT",
                "NOT_CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Рабочую версию «увеит» у пациента подтвердить пока не удалось; вопрос остаётся открытым.",
            ),
            (
                "катаракта",
                "CONDITION",
                "FAMILY",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Сейчас катаракта установлена у бабушки пациента, о ней и идёт речь в семейном анамнезе.",
            ),
            (
                "Тимолол",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "NOT_STARTED",
                "CURRENT",
                "Пациенту выписали Тимолол, однако флакон ещё не открывался: ни одного применения не было.",
            ),
            (
                "Латанопрост",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "PRESCRIBED",
                "FUTURE",
                "Следующее назначение пациенту: Латанопрост с первого числа следующего месяца; сведения о начале отсутствуют.",
            ),
        ],
    ),
    (
        "h02",
        "held-out",
        "Контрольная запись после травмы",
        "lines",
        [
            (
                "вывих",
                "CONDITION",
                "PATIENT",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "HISTORICAL",
                "Достоверно перенесённое пациентом событие в 2020 году — вывих плечевого сустава.",
            ),
            (
                "онемение",
                "SYMPTOM",
                "PATIENT",
                "NEGATED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Сейчас пациент говорит, что онемение не ощущает.",
            ),
            (
                "тендинит",
                "CONDITION",
                "PATIENT",
                "SUSPECTED",
                "NOT_APPLICABLE",
                "CURRENT",
                "На момент сегодняшнего осмотра врач допускает у пациента тендинит как возможный диагноз.",
            ),
            (
                "Мелоксикам",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "STOPPED",
                "HISTORICAL",
                "Мелоксикам: пациент завершил приём позавчера, курс закончился.",
            ),
            (
                "Мелоксикам",
                "MEDICATION",
                "OTHER",
                "UNKNOWN",
                "TAKING",
                "CURRENT",
                "Мелоксикам продолжает ежедневно пить супруг пациента; это описание лечения супруга.",
            ),
            (
                "сколиоз",
                "CONDITION",
                "UNKNOWN",
                "UNKNOWN",
                "NOT_APPLICABLE",
                "UNKNOWN",
                "В приложенном листе встречается слово «сколиоз», но чей это лист и утверждается ли диагноз, выяснить нельзя.",
            ),
        ],
    ),
    (
        "h03",
        "held-out",
        "Clinical note / medication reconciliation",
        "paragraphs",
        [
            (
                "wheezing",
                "SYMPTOM",
                "PATIENT",
                "NEGATED",
                "NOT_APPLICABLE",
                "CURRENT",
                "The patient reports that wheezing is absent today.",
            ),
            (
                "eczema",
                "CONDITION",
                "FAMILY",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "The patient’s father has a confirmed current diagnosis of eczema.",
            ),
            (
                "pneumonia",
                "CONDITION",
                "PATIENT",
                "RULED_OUT",
                "NOT_APPLICABLE",
                "CURRENT",
                "The clinician has ruled out pneumonia in the patient at this visit.",
            ),
            (
                "Cetirizine",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "NOT_STARTED",
                "CURRENT",
                "Cetirizine was prescribed for the patient, but the patient has never taken a single dose.",
            ),
            (
                "Loratadine",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "TAKING",
                "CURRENT",
                "The patient is currently taking Loratadine every morning.",
            ),
            (
                "urticaria",
                "CONDITION",
                "PATIENT",
                "NOT_CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "The patient’s possible urticaria has not been confirmed; further assessment is pending and it has not been ruled out.",
            ),
        ],
    ),
    (
        "h04",
        "held-out",
        "Запись по итогам сверки анамнеза",
        "paired",
        [
            (
                "тиреоидит",
                "CONDITION",
                "PATIENT",
                "SUSPECTED",
                "NOT_APPLICABLE",
                "CURRENT",
                "В отношении пациента тиреоидит сейчас рассматривается врачом лишь как предположение.",
            ),
            (
                "анемия",
                "CONDITION",
                "PATIENT",
                "RULED_OUT",
                "NOT_APPLICABLE",
                "CURRENT",
                "После завершения обследования анемия у пациента отвергнута, диагноз исключён.",
            ),
            (
                "утомляемость",
                "SYMPTOM",
                "PATIENT",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Повод обращения пациента сегодня — выраженная утомляемость.",
            ),
            (
                "Левотироксин",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
                "На старой карточке пациента значится Левотироксин; сведений о его назначении и фактическом использовании нет.",
            ),
            (
                "Фолиевая кислота",
                "MEDICATION",
                "PATIENT",
                "UNKNOWN",
                "NOT_TAKING",
                "CURRENT",
                "Фолиевая кислота сейчас пациентом не принимается; был ли приём раньше, неизвестно.",
            ),
            (
                "остеопороз",
                "CONDITION",
                "OTHER",
                "CONFIRMED",
                "NOT_APPLICABLE",
                "CURRENT",
                "Супруга пациента наблюдается с установленным диагнозом остеопороз, актуальным для неё сейчас.",
            ),
        ],
    ),
]
FIELDS = (
    "name",
    "kind",
    "subject",
    "assertion",
    "medicationState",
    "temporality",
    "sourceText",
)


def main():
    root = Path(__file__).resolve().parents[1] / "evaluation/ingestion-visits-v2"
    if root.exists():
        raise SystemExit("Refusing to overwrite frozen fixtures.")
    root.mkdir(parents=True)
    (root / ".gitattributes").write_text("*.txt -text\n", encoding="utf-8")
    cases = []
    review = [
        "# Проверка эталонной разметки — требуется человек",
        "",
        "Все документы синтетические. Первичная разметка подготовлена AI; независимая проверка НЕ выполнена.",
        "Для каждой записи сверить субъект, отрицание/неподтверждение/исключение, лекарственное событие и временную роль. Не выводить диагноз из медицинских знаний.",
        "При неоднозначности отметить её; не подгонять gold под ответ модели. Исправления оформлять новой версией, сохранять исходную и причину.",
        "Проверяющий: ____ Дата: ____ Результат: НЕ ПРОВЕРЕНО",
        "",
    ]
    for ident, split, title, layout, values in CASES:
        rows = [dict(zip(FIELDS, row)) for row in values]
        for row in rows:
            row["name"] = re.search(re.escape(row["name"]), row["sourceText"], re.I).group()
        sentences = [r["sourceText"] for r in rows]
        if layout == "paired":
            paragraphs = [
                " ".join(sentences[i : i + 2]) for i in range(0, len(sentences), 2)
            ]
        elif layout == "lines":
            paragraphs = [
                "\n".join("- " + s for s in sentences[:3]),
                "\n".join("- " + s for s in sentences[3:]),
            ]
        else:
            paragraphs = sentences
        text = (
            "Врачебное заключение / SYNTHETIC ONLY\n"
            + title
            + "\nНе реальный пациент.\n\n"
            + "\n\n".join(paragraphs)
            + "\n"
        )
        raw = text.encode()
        for n, row in enumerate(rows):
            assert (
                row["name"] in row["sourceText"] and text.count(row["sourceText"]) == 1
            )
            row["contextText"] = next(p for p in paragraphs if row["sourceText"] in p)
            review.extend(
                [
                    f"## {ident}:{n}",
                    row["sourceText"],
                    " | ".join(f"{f}={row[f]}" for f in FIELDS[:-1]),
                    "Решение проверяющего / исправление / основание: ____",
                    "",
                ]
            )
        name = ident + ".txt"
        (root / name).write_bytes(raw)
        cases.append(
            {
                "id": ident,
                "split": split,
                "layout": layout,
                "originalFile": name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "statements": rows,
            }
        )
    manifest = {
        "schemaVersion": "visit-gold-v2",
        "goldReview": "AI-authored; independent human review pending, worksheet GOLD_REVIEW.md.",
        "scope": "10 new fictional documents / 60 assertions: 6 development, 4 held-out. Paired prose, bullets, repeated names with distinct subjects/times, bilingual material. Small correlated synthetic set.",
        "cases": cases,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "GOLD_REVIEW.md").write_text(
        "\n".join(review), encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
