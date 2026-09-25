# Проверка эталонной разметки — требуется человек

Все документы синтетические. Первичная разметка подготовлена AI; независимая проверка НЕ выполнена.
Для каждой записи сверить субъект, отрицание/неподтверждение/исключение, лекарственное событие и временную роль. Не выводить диагноз из медицинских знаний.
При неоднозначности отметить её; не подгонять gold под ответ модели. Исправления оформлять новой версией, сохранять исходную и причину.
Проверяющий: ____ Дата: ____ Результат: НЕ ПРОВЕРЕНО

## d01:0
Пациент уточняет: двоение отсутствует даже при чтении.
name=двоение | kind=SYMPTOM | subject=PATIENT | assertion=NEGATED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d01:1
При этом головокружение у пациента сохраняется.
name=головокружение | kind=SYMPTOM | subject=PATIENT | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d01:2
У отца пациента диабет подтверждён и остаётся актуальным диагнозом.
name=диабет | kind=CONDITION | subject=FAMILY | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d01:3
У самого пациента диабет пока не подтверждён; обследование не закончено.
name=диабет | kind=CONDITION | subject=PATIENT | assertion=NOT_CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d01:4
План: Амлодипин назначен пациенту со следующего вторника, сведений о фактическом старте нет.
name=Амлодипин | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=PRESCRIBED | temporality=FUTURE
Решение проверяющего / исправление / основание: ____

## d01:5
Метформин пациенту выписали месяц назад, но он так и не принял ни одной таблетки.
name=Метформин | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=NOT_STARTED | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d02:0
Варфарин принимает супруга; пациент рассказывает о её текущем лечении.
name=Варфарин | kind=MEDICATION | subject=OTHER | assertion=UNKNOWN | medicationState=TAKING | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d02:1
Бисопролол пациент сейчас не принимает; принимал ли когда-либо, установить не удалось.
name=Бисопролол | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=NOT_TAKING | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d02:2
После обследования аритмия у пациента исключена.
name=аритмия | kind=CONDITION | subject=PATIENT | assertion=RULED_OUT | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d02:3
На листке написано только «астма»; принадлежность листка и статус диагноза неизвестны.
name=астма | kind=CONDITION | subject=UNKNOWN | assertion=UNKNOWN | medicationState=NOT_APPLICABLE | temporality=UNKNOWN
Решение проверяющего / исправление / основание: ____

## d02:4
Кашель? Ответ пациента на приёме: нет, кашель не беспокоит.
name=Кашель | kind=SYMPTOM | subject=PATIENT | assertion=NEGATED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d02:5
У родной сестры пациента подтверждена гипертония, она продолжает наблюдаться.
name=гипертония | kind=CONDITION | subject=FAMILY | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d03:0
Первый курс: Ибупрофен пациент завершил в феврале 2025 года.
name=Ибупрофен | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=STOPPED | temporality=HISTORICAL
Решение проверяющего / исправление / основание: ____

## d03:1
Новый курс: Ибупрофен пациент фактически принимает сейчас по согласованной схеме.
name=Ибупрофен | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=TAKING | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d03:2
В 2019 году у пациента был подтверждён перелом лучевой кости.
name=перелом | kind=CONDITION | subject=PATIENT | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=HISTORICAL
Решение проверяющего / исправление / основание: ____

## d03:3
Текущее предположение врача для пациента — артрит, диагноз ещё проверяется.
name=артрит | kind=CONDITION | subject=PATIENT | assertion=SUSPECTED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d03:4
Сегодня при осмотре пациента сохраняется отёк кисти.
name=отёк | kind=SYMPTOM | subject=PATIENT | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d03:5
Подозревавшаяся у пациента подагра не подтверждена, исключить её пока тоже нельзя.
name=подагра | kind=CONDITION | subject=PATIENT | assertion=NOT_CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d04:0
Врач: беспокоит ли тошнота сейчас? Пациент: нет, тошнота отсутствует.
name=тошнота | kind=SYMPTOM | subject=PATIENT | assertion=NEGATED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d04:1
Врач: а головная боль? Пациент: да, сейчас есть головная боль.
name=головная боль | kind=SYMPTOM | subject=PATIENT | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d04:2
Мать пациента перенесла подтверждённый инсульт в 2017 году.
name=инсульт | kind=CONDITION | subject=FAMILY | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=HISTORICAL
Решение проверяющего / исправление / основание: ____

## d04:3
У пациента острый инсульт по результатам обследования исключён.
name=инсульт | kind=CONDITION | subject=PATIENT | assertion=RULED_OUT | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d04:4
Напроксен указан в карточке пациента без сведений о назначении, приёме или отмене.
name=Напроксен | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=UNKNOWN | temporality=UNKNOWN
Решение проверяющего / исправление / основание: ____

## d04:5
Врач назначил пациенту Парацетамол на завтра; факт приёма не установлен.
name=Парацетамол | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=PRESCRIBED | temporality=FUTURE
Решение проверяющего / исправление / основание: ____

## d05:0
Омепразол: пациент подтвердил, что принимает его ежедневно в настоящее время.
name=Омепразол | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=TAKING | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d05:1
Фамотидин: рецепт был выдан, но пациент сообщает, что лечение им вообще не начинал.
name=Фамотидин | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=NOT_STARTED | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d05:2
Панкреатит в прошлом пациент отрицает.
name=Панкреатит | kind=CONDITION | subject=PATIENT | assertion=NEGATED | medicationState=NOT_APPLICABLE | temporality=HISTORICAL
Решение проверяющего / исправление / основание: ____

## d05:3
Предположение для пациента на текущем приёме: язва; подтверждающих результатов пока нет.
name=язва | kind=CONDITION | subject=PATIENT | assertion=SUSPECTED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d05:4
У соседа пациента имеется подтверждённый цирроз; это сведения исключительно о соседе.
name=цирроз | kind=CONDITION | subject=OTHER | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d05:5
По словам пациента, рвота отсутствует.
name=рвота | kind=SYMPTOM | subject=PATIENT | assertion=NEGATED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d06:0
Подтверждённый текущий диагноз пациента: бронхит.
name=бронхит | kind=CONDITION | subject=PATIENT | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d06:1
У пациента пневмония не подтверждена, но обследование ещё продолжается.
name=пневмония | kind=CONDITION | subject=PATIENT | assertion=NOT_CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d06:2
У пациента туберкулёз окончательно исключён врачом.
name=туберкулёз | kind=CONDITION | subject=PATIENT | assertion=RULED_OUT | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## d06:3
Преднизолон пациенту отменили пять дней назад, он прекратил курс.
name=Преднизолон | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=STOPPED | temporality=HISTORICAL
Решение проверяющего / исправление / основание: ____

## d06:4
Сальбутамол упомянут в списке пациента; установить, назначен ли он и используется ли, не удалось.
name=Сальбутамол | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=UNKNOWN | temporality=UNKNOWN
Решение проверяющего / исправление / основание: ____

## d06:5
На сегодняшнем приёме пациент жалуется на одышку при обычной ходьбе.
name=одышку | kind=SYMPTOM | subject=PATIENT | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h01:0
Со слов пациента на сегодняшний день светобоязнь полностью отсутствует.
name=светобоязнь | kind=SYMPTOM | subject=PATIENT | assertion=NEGATED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h01:1
В отличие от этого, слезотечение пациента сегодня беспокоит.
name=слезотечение | kind=SYMPTOM | subject=PATIENT | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h01:2
Рабочую версию «увеит» у пациента подтвердить пока не удалось; вопрос остаётся открытым.
name=увеит | kind=CONDITION | subject=PATIENT | assertion=NOT_CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h01:3
Сейчас катаракта установлена у бабушки пациента, о ней и идёт речь в семейном анамнезе.
name=катаракта | kind=CONDITION | subject=FAMILY | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h01:4
Пациенту выписали Тимолол, однако флакон ещё не открывался: ни одного применения не было.
name=Тимолол | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=NOT_STARTED | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h01:5
Следующее назначение пациенту: Латанопрост с первого числа следующего месяца; сведения о начале отсутствуют.
name=Латанопрост | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=PRESCRIBED | temporality=FUTURE
Решение проверяющего / исправление / основание: ____

## h02:0
Достоверно перенесённое пациентом событие в 2020 году — вывих плечевого сустава.
name=вывих | kind=CONDITION | subject=PATIENT | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=HISTORICAL
Решение проверяющего / исправление / основание: ____

## h02:1
Сейчас пациент говорит, что онемение не ощущает.
name=онемение | kind=SYMPTOM | subject=PATIENT | assertion=NEGATED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h02:2
На момент сегодняшнего осмотра врач допускает у пациента тендинит как возможный диагноз.
name=тендинит | kind=CONDITION | subject=PATIENT | assertion=SUSPECTED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h02:3
Мелоксикам: пациент завершил приём позавчера, курс закончился.
name=Мелоксикам | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=STOPPED | temporality=HISTORICAL
Решение проверяющего / исправление / основание: ____

## h02:4
Мелоксикам продолжает ежедневно пить супруг пациента; это описание лечения супруга.
name=Мелоксикам | kind=MEDICATION | subject=OTHER | assertion=UNKNOWN | medicationState=TAKING | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h02:5
В приложенном листе встречается слово «сколиоз», но чей это лист и утверждается ли диагноз, выяснить нельзя.
name=сколиоз | kind=CONDITION | subject=UNKNOWN | assertion=UNKNOWN | medicationState=NOT_APPLICABLE | temporality=UNKNOWN
Решение проверяющего / исправление / основание: ____

## h03:0
The patient reports that wheezing is absent today.
name=wheezing | kind=SYMPTOM | subject=PATIENT | assertion=NEGATED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h03:1
The patient’s father has a confirmed current diagnosis of eczema.
name=eczema | kind=CONDITION | subject=FAMILY | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h03:2
The clinician has ruled out pneumonia in the patient at this visit.
name=pneumonia | kind=CONDITION | subject=PATIENT | assertion=RULED_OUT | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h03:3
Cetirizine was prescribed for the patient, but the patient has never taken a single dose.
name=Cetirizine | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=NOT_STARTED | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h03:4
The patient is currently taking Loratadine every morning.
name=Loratadine | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=TAKING | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h03:5
The patient’s possible urticaria has not been confirmed; further assessment is pending and it has not been ruled out.
name=urticaria | kind=CONDITION | subject=PATIENT | assertion=NOT_CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h04:0
В отношении пациента тиреоидит сейчас рассматривается врачом лишь как предположение.
name=тиреоидит | kind=CONDITION | subject=PATIENT | assertion=SUSPECTED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h04:1
После завершения обследования анемия у пациента отвергнута, диагноз исключён.
name=анемия | kind=CONDITION | subject=PATIENT | assertion=RULED_OUT | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h04:2
Повод обращения пациента сегодня — выраженная утомляемость.
name=утомляемость | kind=SYMPTOM | subject=PATIENT | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h04:3
На старой карточке пациента значится Левотироксин; сведений о его назначении и фактическом использовании нет.
name=Левотироксин | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=UNKNOWN | temporality=UNKNOWN
Решение проверяющего / исправление / основание: ____

## h04:4
Фолиевая кислота сейчас пациентом не принимается; был ли приём раньше, неизвестно.
name=Фолиевая кислота | kind=MEDICATION | subject=PATIENT | assertion=UNKNOWN | medicationState=NOT_TAKING | temporality=CURRENT
Решение проверяющего / исправление / основание: ____

## h04:5
Супруга пациента наблюдается с установленным диагнозом остеопороз, актуальным для неё сейчас.
name=остеопороз | kind=CONDITION | subject=OTHER | assertion=CONFIRMED | medicationState=NOT_APPLICABLE | temporality=CURRENT
Решение проверяющего / исправление / основание: ____
