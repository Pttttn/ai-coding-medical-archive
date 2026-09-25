"""Freeze synthetic VISIT originals and scorer-only labels; never overwrite a frozen set."""
import hashlib
import json
from pathlib import Path

# name | kind | subject | assertion | medicationState | temporality | original sentence
# Labels describe the source statement, not clinical truth. All cases are fictional.
CASES = [
('v01', 'development', 'Первичный приём терапевта', [
'гипертония|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|У пациента установлена гипертония, диагноз сохраняется.',
'диабет|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|HISTORICAL|У матери был диагностирован диабет.',
'стенокардия|CONDITION|PATIENT|SUSPECTED|NOT_APPLICABLE|CURRENT|У пациента подозревается стенокардия, обследование продолжается.',
'пневмония|CONDITION|PATIENT|RULED_OUT|NOT_APPLICABLE|CURRENT|Пневмония у пациента исключена по результатам обследования.',
'Амлодипин|MEDICATION|PATIENT|UNKNOWN|TAKING|CURRENT|Амлодипин пациент принимает сейчас по 5 мг утром.',
'Аторвастатин|MEDICATION|PATIENT|UNKNOWN|NOT_STARTED|CURRENT|Аторвастатин назначен ранее, но пациент его до сих пор не начал принимать.',
'головная боль|SYMPTOM|PATIENT|NEGATED|NOT_APPLICABLE|CURRENT|Сейчас головная боль пациентом отрицается.',
]),
('v02', 'development', 'Повторное эндокринологическое заключение', [
'гипотиреоз|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|У пациента подтверждён гипотиреоз; состояние актуально.',
'диабет|CONDITION|PATIENT|NOT_CONFIRMED|NOT_APPLICABLE|CURRENT|Диабет пока не подтверждён, для исключения данных недостаточно.',
'ожирение|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|CURRENT|У отца имеется ожирение.',
'Метформин|MEDICATION|PATIENT|UNKNOWN|PRESCRIBED|FUTURE|Назначен Метформин 500 мг вечером с завтрашнего дня; факт начала приёма не известен.',
'Левотироксин|MEDICATION|PATIENT|UNKNOWN|TAKING|CURRENT|Пациент ежедневно принимает Левотироксин 50 мкг.',
'слабость|SYMPTOM|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|Пациента сейчас беспокоит слабость.',
'тиреоидит|CONDITION|UNKNOWN|UNKNOWN|NOT_APPLICABLE|UNKNOWN|В неатрибутированной выписке упомянут тиреоидит; кому принадлежит запись, неизвестно.',
]),
('v03', 'development', 'Осмотр невролога после травмы', [
'сотрясение|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|HISTORICAL|В 2021 году у пациента было подтверждено сотрясение.',
'эпилепсия|CONDITION|PATIENT|SUSPECTED|NOT_APPLICABLE|CURRENT|На этом приёме у пациента подозревается эпилепсия.',
'инсульт|CONDITION|PATIENT|RULED_OUT|NOT_APPLICABLE|CURRENT|Острый инсульт у пациента исключён.',
'мигрень|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|CURRENT|У сестры пациента установлена мигрень.',
'Ибупрофен|MEDICATION|PATIENT|UNKNOWN|STOPPED|HISTORICAL|Ибупрофен пациент прекратил принимать в прошлом месяце.',
'Напроксен|MEDICATION|PATIENT|UNKNOWN|NOT_TAKING|CURRENT|Пациент сейчас не принимает Напроксен; ранее мог принимать, сведений нет.',
'головокружение|SYMPTOM|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|Сегодня пациент отмечает головокружение.',
]),
('v04', 'development', 'Кардиологическое наблюдение', [
'аритмия|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|По ЭКГ у пациента подтверждена аритмия.',
'кардиомиопатия|CONDITION|PATIENT|NOT_CONFIRMED|NOT_APPLICABLE|CURRENT|Кардиомиопатия не подтверждена, обследование пациента не завершено.',
'инфаркт|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|HISTORICAL|Отец перенёс инфаркт в 2018 году.',
'Бисопролол|MEDICATION|PATIENT|UNKNOWN|TAKING|CURRENT|Пациент сейчас принимает Бисопролол 2,5 мг ежедневно.',
'Аспирин|MEDICATION|PATIENT|UNKNOWN|STOPPED|HISTORICAL|Аспирин отменён пациенту неделю назад.',
'Варфарин|MEDICATION|OTHER|UNKNOWN|TAKING|CURRENT|Супруг пациента принимает Варфарин; это сведения о супруге.',
'одышка|SYMPTOM|PATIENT|NEGATED|NOT_APPLICABLE|CURRENT|Одышка сейчас пациентом отрицается.',
]),
('v05', 'development', 'Консультация гастроэнтеролога', [
'гастрит|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|У пациента подтверждён гастрит.',
'язва|CONDITION|PATIENT|SUSPECTED|NOT_APPLICABLE|CURRENT|У пациента подозревается язва, назначена диагностика.',
'панкреатит|CONDITION|PATIENT|NEGATED|NOT_APPLICABLE|HISTORICAL|Перенесённый панкреатит пациент отрицает.',
'Омепразол|MEDICATION|PATIENT|UNKNOWN|PRESCRIBED|FUTURE|Омепразол назначен пациенту с понедельника; приём ещё не оценивался.',
'Фамотидин|MEDICATION|PATIENT|UNKNOWN|NOT_STARTED|CURRENT|Фамотидин пациент не начинал принимать, хотя рецепт уже выдан.',
'цирроз|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|HISTORICAL|У бабушки ранее был диагностирован цирроз.',
'тошнота|SYMPTOM|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|Сегодня у пациента сохраняется тошнота.',
]),
('v06', 'development', 'Пульмонологический осмотр', [
'астма|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|У пациента подтверждена астма, наблюдение продолжается.',
'туберкулёз|CONDITION|PATIENT|RULED_OUT|NOT_APPLICABLE|CURRENT|Активный туберкулёз у пациента исключён.',
'бронхит|CONDITION|PATIENT|SUSPECTED|NOT_APPLICABLE|CURRENT|Врач подозревает у пациента бронхит.',
'Сальбутамол|MEDICATION|PATIENT|UNKNOWN|TAKING|CURRENT|Пациент использует Сальбутамол по назначению в настоящее время.',
'Преднизолон|MEDICATION|PATIENT|UNKNOWN|STOPPED|HISTORICAL|Курс препарата Преднизолон пациент завершил в прошлом году.',
'кашель|SYMPTOM|PATIENT|NEGATED|NOT_APPLICABLE|CURRENT|На момент осмотра кашель пациент отрицает.',
'эмфизема|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|CURRENT|У брата пациента имеется эмфизема.',
]),
('v07', 'development', 'Разбор анамнеза на приёме', [
'анемия|CONDITION|PATIENT|NOT_CONFIRMED|NOT_APPLICABLE|CURRENT|Анемия у пациента пока не подтверждена, анализ повторят.',
'гемофилия|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|CURRENT|У дяди пациента установлена гемофилия.',
'тромбоз|CONDITION|PATIENT|RULED_OUT|NOT_APPLICABLE|CURRENT|Тромбоз у пациента исключён на текущем обследовании.',
'Цианокобаламин|MEDICATION|PATIENT|UNKNOWN|UNKNOWN|UNKNOWN|В списке есть Цианокобаламин, статус приёма пациентом неизвестен.',
'Фолиевая кислота|MEDICATION|PATIENT|UNKNOWN|TAKING|CURRENT|Фолиевая кислота принимается пациентом ежедневно в дозе 1 мг.',
'сердцебиение|SYMPTOM|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|Пациент жалуется сейчас на сердцебиение.',
'лейкоз|CONDITION|UNKNOWN|UNKNOWN|NOT_APPLICABLE|UNKNOWN|В архивной заметке без указания человека написано: лейкоз; иных сведений нет.',
]),
('v08', 'development', 'Заключение ревматолога', [
'артрит|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|Диагноз артрит у пациента подтверждён на этом приёме.',
'подагра|CONDITION|PATIENT|SUSPECTED|NOT_APPLICABLE|CURRENT|Врач рассматривает у пациента диагноз подагра как подозрение.',
'волчанка|CONDITION|PATIENT|NOT_CONFIRMED|NOT_APPLICABLE|CURRENT|Диагноз волчанка у пациента не подтверждён, но ещё не исключён.',
'Диклофенак|MEDICATION|PATIENT|UNKNOWN|NOT_TAKING|CURRENT|Пациент не принимает Диклофенак в настоящее время.',
'Мелоксикам|MEDICATION|PATIENT|UNKNOWN|PRESCRIBED|FUTURE|Пациенту назначен Мелоксикам на следующую неделю; приём не подтверждался.',
'остеопороз|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|CURRENT|Мать пациента наблюдается с подтверждённым диагнозом остеопороз.',
'лихорадка|SYMPTOM|PATIENT|NEGATED|NOT_APPLICABLE|CURRENT|Лихорадка у пациента на осмотре отсутствует.',
]),
('v09', 'held-out', 'Сводка очной беседы с дерматологом', [
'псориаз|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|Обсудили текущий подтверждённый диагноз пациента: псориаз.',
'экзема|CONDITION|PATIENT|SUSPECTED|NOT_APPLICABLE|CURRENT|Что касается пациента, экзема остаётся рабочей гипотезой врача.',
'меланома|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|HISTORICAL|Пациент вспомнил, что у матери в прошлом была меланома.',
'Цетиризин|MEDICATION|PATIENT|UNKNOWN|NOT_STARTED|CURRENT|Рецепт на Цетиризин пациент получил, упаковку купил; ни одной дозы не принял.',
'Лоратадин|MEDICATION|PATIENT|UNKNOWN|STOPPED|HISTORICAL|От лекарства Лоратадин пациент отказался месяц назад и прекратил курс.',
'зуд|SYMPTOM|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|Основная жалоба пациента сегодня — зуд.',
'чесотка|CONDITION|PATIENT|RULED_OUT|NOT_APPLICABLE|CURRENT|После обследования диагноз чесотка у пациента окончательно исключили.',
]),
('v10', 'held-out', 'Выписка из протокола беседы уролога', [
'цистит|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|Врач подтвердил пациенту диагноз цистит на текущем приёме.',
'пиелонефрит|CONDITION|PATIENT|NOT_CONFIRMED|NOT_APPLICABLE|CURRENT|Сведений недостаточно: пиелонефрит у пациента не подтверждён, окончательно не исключён.',
'Нитрофурантоин|MEDICATION|PATIENT|UNKNOWN|TAKING|CURRENT|На вопрос о лечении пациент ответил: Нитрофурантоин принимаю каждый день.',
'Фосфомицин|MEDICATION|PATIENT|UNKNOWN|PRESCRIBED|FUTURE|В плане для пациента Фосфомицин на завтра, врач выписал рецепт, приём не установлен.',
'гематурия|SYMPTOM|PATIENT|NEGATED|NOT_APPLICABLE|CURRENT|Пациент ответил отрицательно на вопрос, есть ли сейчас гематурия.',
'нефролитиаз|CONDITION|FAMILY|CONFIRMED|NOT_APPLICABLE|CURRENT|Нефролитиаз имеется у родного брата, со слов пациента диагноз брату подтверждён.',
'Тамсулозин|MEDICATION|OTHER|UNKNOWN|TAKING|CURRENT|Сосед пациента принимает Тамсулозин; это пример соседа, не пациента.',
]),
('v11', 'held-out', 'Запись беседы офтальмолога', [
'катаракта|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|CURRENT|По итогам сегодняшнего осмотра диагноз пациента катаракта считается установленным.',
'глаукома|CONDITION|PATIENT|SUSPECTED|NOT_APPLICABLE|CURRENT|Для пациента пока остаётся подозрение: глаукома; предстоит обследование.',
'увеит|CONDITION|PATIENT|RULED_OUT|NOT_APPLICABLE|CURRENT|Врач завершил обследование пациента и исключил увеит.',
'Тимолол|MEDICATION|PATIENT|UNKNOWN|NOT_TAKING|CURRENT|Тимолол пациент на данный момент не использует; начинал ли раньше, неизвестно.',
'Травопрост|MEDICATION|PATIENT|UNKNOWN|UNKNOWN|UNKNOWN|Травопрост значится в старой карточке пациента без сведений о назначении либо применении.',
'двоение|SYMPTOM|PATIENT|NEGATED|NOT_APPLICABLE|CURRENT|Пациент сообщает, что двоение сейчас отсутствует.',
'ретинопатия|CONDITION|UNKNOWN|UNKNOWN|NOT_APPLICABLE|UNKNOWN|Чужая или собственная запись — неясно: ретинопатия. Принадлежность записи не установлена.',
]),
('v12', 'held-out', 'Стенограмма контрольного ЛОР-приёма', [
'отит|CONDITION|PATIENT|CONFIRMED|NOT_APPLICABLE|HISTORICAL|Пациент рассказал о подтверждённом заболевании в детстве: отит.',
'синусит|CONDITION|PATIENT|SUSPECTED|NOT_APPLICABLE|CURRENT|На сегодняшнем приёме врач предполагает у пациента синусит.',
'тонзиллит|CONDITION|PATIENT|NOT_CONFIRMED|NOT_APPLICABLE|CURRENT|Для пациента тонзиллит пока не доказан; врач ещё не может его исключить.',
'Амоксициллин|MEDICATION|PATIENT|UNKNOWN|STOPPED|HISTORICAL|Пациент больше не пьёт Амоксициллин, курс закончен три дня назад.',
'Мометазон|MEDICATION|PATIENT|UNKNOWN|TAKING|CURRENT|Из текущей терапии пациент указал Мометазон: применяет по два впрыскивания ежедневно.',
'снижение слуха|SYMPTOM|FAMILY|CONFIRMED|NOT_APPLICABLE|CURRENT|Пациент сообщил, что у отца сейчас отмечается снижение слуха.',
'осиплость|SYMPTOM|PATIENT|NEGATED|NOT_APPLICABLE|CURRENT|На прямой вопрос пациент ответил: осиплость сегодня не беспокоит.',
]),
]


def main():
    root = Path(__file__).resolve().parents[1] / 'evaluation/ingestion-visits-v1'
    if root.exists():
        raise SystemExit('Refusing to overwrite frozen fixtures.')
    root.mkdir(parents=True)
    (root / '.gitattributes').write_text('*.txt -text\n', encoding='utf-8')
    cases = []
    fields = ['name', 'kind', 'subject', 'assertion', 'medicationState', 'temporality', 'sourceText']
    for ident, split, title, lines in CASES:
        rows = [dict(zip(fields, line.split('|'))) for line in lines]
        # Development uses separated statements; held-out uses pairs within paragraphs.
        paragraphs = [r['sourceText'] for r in rows]
        if split == 'held-out':
            paragraphs = [' '.join(paragraphs[i:i+2]) for i in range(0, len(paragraphs), 2)]
        text = 'Врачебное заключение\nСИНТЕТИЧЕСКИЙ ПРИМЕР. Не реальный пациент.\n' + title + '\n\n' + '\n\n'.join(paragraphs) + '\n'
        raw = text.encode('utf-8')
        for row in rows:
            row['contextText'] = next(p for p in paragraphs if row['sourceText'] in p)
        filename = ident + '.txt'
        (root / filename).write_bytes(raw)
        cases.append({'id': ident, 'split': split, 'originalFile': filename,
                      'sha256': hashlib.sha256(raw).hexdigest(), 'statements': rows})
    manifest = {'schemaVersion': 'visit-gold-v1', 'goldReview': 'AI-authored synthetic gold; no independent clinical review.',
                'scope': '12 fictional visits / 84 statements. Explicit source assertions; held-out has different specialties and paired prose. Small correlated set, not clinical validation.',
                'cases': cases}
    (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
