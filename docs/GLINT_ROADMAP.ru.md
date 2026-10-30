# Glint: план проверки и развития

## Текущий результат 001–073 — 30 октября 2026

### Выбран 001–074; проверенный бинарник пока 001–073

**Исправлена гонка локального хранилища при сохранении настроек профиля.** Чтение accounts/settings
теперь использует тот же существующий RLock, что и атомарные записи; форматы файлов, таймауты
и обработка повреждённых документов не менялись. На отдельном Windows-профиле до исправления:
214 пустых чтений и 247 ошибок записи из 500 попыток; после: **500/500 записей, 0 ошибок и 0 пустых чтений**.
Целевые storage/QML-проверки прошли **56/56**, включая обе задержки refresh.
[Воспроизведение и исправление](../native/drafts/environment/storage-read-lock74-observations.json).

Предыдущий полный повтор: **4576 passed, 1 failed, 1 skipped** — чтение пустого списка аккаунтов
в QML во время сохранения. Это отдельный сбой, не прежний deadline доставки нового профиля;
[отрицательный результат сохранён](../native/drafts/environment/canonical-python74-qml-save-failure-observations.json).
Полного зелёного прогона после storage-исправления пока нет. Межпроцессная блокировка этим не заявляется.

Полный Python-прогон после выбора 074 завершён: **4575 passed, 1 failed, 1 skipped**;
контроль исходников/статуса прошёл. Единственный сбой — исторический тест 0070 ошибочно
требовал отсутствие новых native-групп. Исправлено сравнение с точным историческим префиксом,
без удаления старых cases. Целевой повтор: **180/180**. Полный повтор после этого исправления
ещё нужен; исходный отрицательный результат [сохранён](../native/drafts/environment/canonical-python74-history-failure-observations.json).

Связанный пакет 0074 зарегистрирован; checkpoint 001–073 и сохранённый runtime не менялись.
Добавлены обязательные `screen-live-main` / `screen-dispatch`: **23 группы, 494 native-кейса**,
включая прежние 488 и шесть новых. **1179 Python-проверок прошли, 1 skipped** после обновления
release-контракта и восстановления исторического verifier через обратимый test-only patch.
[Выбор](../native/drafts/environment/screen74-selection-observations.json).

Сборка **не запущена**: на D: около 110 ГиБ свободно при обязательном резерве 180 ГиБ.
Проверка остановилась до изменения Chromium-исходников; лимит не снижен, старые runtime/профили
не удалялись. Широкая read-only оценка остановлена ради уменьшения параллельного metadata I/O
во время тестов; полный размер каталогов не установлен. Shallow-проверка нашла лишь 1,77 ГиБ
крупных report.json — этого недостаточно, чтобы восстановить требуемый резерв.
[Preflight](../native/drafts/environment/screen74-build-preflight-observations.json).
После освобождения резерва: связанная сборка на j4 → все 494 native-кейса → исходный CDP stress
и защищённый BFCache, без ослабления критериев. До этого исправление не считается работающим.

### Новый защищённый BFCache-прогон

Полный Python-повтор с этим collector на `f59e578`: **4568 passed, 1 skipped**, 6м23с;
исходники и рабочее дерево не изменились во время проверки.
[Результат](../native/drafts/environment/canonical-python73-protected-history-observations.json).

Подготовлен [следующий связанный C++-пакет](../native/drafts/environment/live-screen-linked-next.patch):
browser-side invalidation учитывает logical screen, главный renderer предпочитает актуальный
эмулятор задержанному transport-снимку, clear снимает старый logical override.
Добавлены шесть native-тестов: add/update/clear в browser и live/update/clear в Blink.
Четыре изменённых translation units прошли clang; активные Chromium-исходники не менялись.
На момент preflight патч не был зарегистрирован; теперь выбран 001–074, но эти шесть тестов
ещё не выполнены и runtime-исправление не доказано.
[Подготовка](../native/drafts/environment/live-screen-linked-next-observations.json).

В текущем browser-коде `StoredVisualPropertiesNeedsUpdate` сравнивает физический screen,
но пропускает logical screen: изменение только логических данных не гарантирует отправку
нового snapshot. Следующий этап — зарегистрировать связанный пакет, выполнить все шесть новых
native-кейсов вместе с прежними и повторить исходный CDP stress без ослабления проверок.

[Публичный collector](../native/drafts/environment/first-script/protected_history_runtime.py)
прошёл desktop и Mobile Web: **12 экранных фаз**, по **32 Canvas-варианта до/после BFCache**
в каждом окружении. Включены флаги Canvas/WebGL/AudioMath, но после восстановления
проверялись именно Canvas и экран — это не допуск GPU/Audio во всём lifecycle.
Проверены реальные запрошенные размеры, DPR, шесть документов, сохранённый BFCache,
отсутствие подмены восстановления обычной перезагрузкой. Все 14/13 наблюдавшихся процессов
desktop/Mobile Web завершились; runtime-ресурсы освобождены.
[Результат](../native/drafts/environment/protected-history73-observations.json).

Запуск из корня проекта, без новой сборки:

```powershell
.\.venv\Scripts\python.exe native/drafts/environment/first-script/protected_history_runtime.py --executable D:/Glint156Candidate/preserved-runtime73-20261030-v1/runtime/chrome.exe --work-dir D:/GlintManagerQA/protected-history-new-run --driver-stage D:/GlintManagerQA/staged-python-js70-20261030-v1
```

Выходной каталог должен быть новым. Диагностический staged driver обязателен;
установленный SDK не меняется, production-допуск не выдаётся.

**Пакет собран, 488/488 нативных тестов прошли**, включая четыре строгих orientation-теста.
Инкрементальная сборка: j4, 51 шаг, 43м55с Ninja; полный resume-controller — 59м24с.
269 runtime-файлов сохранены отдельно; объекты не очищались, sync повторно не запускался.
[Сборка](../native/drafts/upstream-156/build73-observations.json),
[нативные проверки](../native/drafts/upstream-156/native-batch73-observations.json).

| Проверка нового бинарника | Результат | Ограничение |
| --- | --- | --- |
| Базовый runtime | [18/18](../native/drafts/upstream-156/runtime-baseline73-observations.json) | Storage, прокси, permissions, Recorder, backup/restore; не защищённые политики |
| Canvas + WebGL + AudioMath | [18/18 фаз](../native/drafts/environment/combined-math73-observations.json) | Baseline + 8 профилей, запуск/перезапуск, оба AudioMath selector; не реалистичный device cohort |
| Canvas formats | [32/32](../native/drafts/environment/canvas-formats73-observations.json) | HTML/Offscreen, sRGB/P3, unorm8/float16 |
| PNG document | [Пройдено](../native/drafts/environment/canvas-export73-observations.json) | Совпадение с пикселями до изменения Canvas и цветовые метаданные |
| Worker formats | [96/96](../native/drafts/environment/worker-formats73-observations.json) | Шесть classic/module-классов; не nested/restart |
| Worker PNG | [24 варианта на профиль](../native/drafts/environment/worker-export73-observations.json) | Document-контроли учитываются отдельно |
| Finite Float16 | [4 контекста](../native/drafts/environment/canvas-hdr73-observations.json) | Alpha, crop/repeat/re-put и ограниченные изменения RGB; не широкая HDR-совместимость |
| Worker Float16 | [12 worker-контекстов на профиль](../native/drafts/environment/worker-hdr73-observations.json) | Согласованность с document; наблюдавшиеся процессы завершены |
| Два одновременных профиля | [6/6 фаз](../native/drafts/environment/combined-concurrent73-observations.json) | Не длительная ресурсная проверка |

**Mobile Web 073: [18/18 фаз](../native/drafts/environment/combined-mobile73-observations.json)**,
оба AudioMath selector; это Windows Web Emulation, не Android/iOS.
Полный Python-повтор на `d0de567`: **4546 passed, 1 skipped**, 6м52с,
контроль исходников/статуса прошёл. Он включает worker HDR, но предшествует тестам новых screen/mobile-записей.
[Python](../native/drafts/environment/canonical-python73-runtime-observations.json).

[Экран в браузере](../native/drafts/environment/screen73-browser-observations.json):
first-script **6/6 фаз**, штатный manager context-options lifecycle **12/12 фаз**,
включая доказанный BFCache для desktop/mobile. Отдельный raw CDP stress **не прошёл**:
разные per-page metrics влияют на screen/DPR соседней страницы и размеры screenshot.
Его отрицательный результат сохранён; общий lifecycle-допуск не выдан.

**Далее:** изоляция raw CDP metrics и защищённый lifecycle → worker restart/nesting → WebGPU/readback
и согласованные устройства → длительные ресурсы → security rebase → пакет/обновление/откат.
Production, внешние антибот-тесты и гарантированный обход CAPTCHA этим не подтверждены.

Ниже сохранены предыдущие снимки результатов; их статусы сборки относятся к соответствующей версии.

## Worker PNG закрыт на 001–072; сборка 0073 возобновляется без очистки

Worker PNG-прогон прошёл **24/24 варианта на каждом baseline/защищённом профиле**:
шесть classic/module dedicated/shared/service workers, четыре Offscreen-формата.
PNG совпадает с пикселями до изменения Canvas, цветовые метаданные сохранены,
результат согласован с document. Точный публичный collector выполнен из локального
снимка исходников 001–072 с соответствующим receipt, отдельно от активной сборки.
[Результат](../native/drafts/environment/worker-export72-observations.json).
Это не проверка 001–073, worker restart/nested или HDR-качества.

Новый finite Float16-прогон прошёл **4/4 HTML/Offscreen × sRGB/P3 контекста**:
negative/HDR/subnormal-сигналы присутствуют; alpha и неopaque-цвета сохранены,
ограничения mantissa/sign/exponent и crop/repeat/re-put соблюдены. Это не широкая
HDR-совместимость редакторов. Первый неподходящий oracle без соседних opaque-пикселей
сохранён отдельно; алгоритм браузера ради теста не менялся.
[Проверка](../native/drafts/environment/canvas-hdr72-observations.json),
[исходный oracle](../native/drafts/environment/canvas-hdr72-initial-oracle-observations.json).

Полный Python-повтор после восстановления исторической привязки:
**4503 passed, 1 skipped**, контроль исходников/статуса прошёл, оба QML-теста доставки
профиля зелёные. Этот полный прогон предшествует новым finite HDR-тестам.
[Полный повтор](../native/drafts/environment/canonical-python73-worker-export-observations.json),
[сохранённый предыдущий сбой](../native/drafts/environment/canonical-python73-diagnostics-failures.json).

После исчезновения процессов сборки успешное завершение 0073 не подтверждено.
Возобновляется только build на j4: sync/hooks/patch завершены, объекты и сохранённый
001–072 не удаляются. До нового бинарника статус коррекции остаётся непроверенным.

## 001–072 проверен шире; выбрана коррекция 0073, не готовый релиз

- **Native: 485/488**, три сбоя новых orientation-тестов. Старые 20 групп прошли
  все 484 случая. Main-frame игнорирует logical screen; computed-тест также попадает
  под принудительный portrait в Blink web-test mode. [Отрицательный результат](../native/drafts/upstream-156/native-batch72-observations.json).
- **0073 выбран:** logical screen применяется и к main-frame; физические API не меняются.
  В тестовом fixture включён реальный, не web-test режим; четыре строгих теста сохранены.
  Два C++ compiler-check прошли, новая сборка и выполнение тестов ещё обязательны.
  [Выбор исходников](../native/drafts/environment/screen73-selection-observations.json).
- **Mobile Web: 18/18** после завершения линковки, без увеличения таймаутов.
  Первый baseline timeout сохранён отдельно, причина не объявлена доказанной.
  [Повтор](../native/drafts/environment/combined-mobile72-observations.json), [сбой](../native/drafts/environment/combined-mobile72-timeout-observations.json).
- **Workers: 96/96** форматов Offscreen в classic/module dedicated/shared/service;
  результаты согласованы с document в каждом профиле. Не включает nested, worker PNG и HDR-качество.
  [Проверки](../native/drafts/environment/worker-formats72-observations.json).
- **Python: 4472 passed, 2 failed, 1 skipped**. Оба сбоя — deadline доставки нового
  профиля в QML; отдельный повтор 2/2 прошёл без правок. Проверка UI под нагрузкой не закрыта.
  [Сохранённые сбои](../native/drafts/environment/canonical-python72-ui-failures.json).

## Новый runtime-результат: combined 18/18, Canvas formats 32/32

На собранном 001–072 прошли **18/18 фаз** совместной проверки Canvas/WebGL/AudioMath:
baseline + 8 защищённых профилей, первый запуск и перезапуск, оба AudioMath selector.
Все наблюдавшиеся процессы завершены, ключи профилей стабильны.
[Результат](../native/drafts/environment/combined-math72-observations.json).

Отдельный форматный прогон теперь проходит **32/32** сочетания HTML/Offscreen,
sRGB/Display-P3, unorm8/float16 и форматов чтения: повторные чтения стабильны,
эффект относительно baseline есть во всех случаях, `NotReadableError` не воспроизводится.
[Результат](../native/drafts/environment/canvas-formats72-observations.json).
PNG-экспорт также прошёл: **8/8 вариантов, 12/12 PNG на baseline и защищённом профиле**,
точное совпадение с пикселями до изменения Canvas и корректные цветовые метаданные.
[Экспорт](../native/drafts/environment/canvas-export72-observations.json).
Два одновременно открытых профиля прошли **6/6 фаз** закрытия соседа и перезапуска;
наблюдавшиеся процессы завершены. [Concurrent](../native/drafts/environment/combined-concurrent72-observations.json).
Остаются workers, HDR-качество, длительная ресурсная проверка и новый Mobile Web.

## 001–072 собран и сохранён; базовый runtime 18/18

Связанный пакет собрался на Windows: **j4, 64 шага, 15м14с**. Отдельно сохранены
269 runtime-файлов; сравнение/откат на 001–070 остаётся доступным.
[Сборка](../native/drafts/upstream-156/build72-observations.json).
На новом бинарнике прошли **18/18 базовых runtime-проверок**, включая storage,
прокси, permissions, Recorder и backup/restore. Это не полный допуск защитных политик.
[Runtime](../native/drafts/upstream-156/runtime-baseline72-observations.json).
Полный Python-повтор после исправления исторических привязок:
**4464 passed, 1 skipped**; далее ещё добавлены тесты публикации результатов.
Теперь обязательны сборка/проверка коррекции 0073 и UI под нагрузкой;
security rebase и релиз по-прежнему не закрыты.

## История: выбор пакета 001–072 до его сборки

В source chain добавлены **0071 orientation/visibility** и **0072 Canvas P3/F16**:
девять изменённых файлов, отдельный строгий gate для четырёх orientation-тестов.
Совместная изолированная копия прошла три дополнительных C++ compiler-check.
Это не запуск этих тестов и не пересобранный Chromium.
[Выбор исходников](../native/drafts/environment/linked72-selection-observations.json).
Переход использует сохранённый 001–070 для сравнения/отката и максимум **j4**;
далее — 21 нативная группа, полный Canvas format matrix и повтор runtime/combined gates.
Полный Python-повтор `ba72a17`: **4447 passed, 1 skipped**, до выбора нового source chain.

## Незакрытая проверка: Canvas Display-P3 / Float16

На сохранённом 001–070 расширенный дифференциальный прогон обнаружил **30 ошибок из 32 сочетаний**:
без защиты Chromium читает все форматы; с защитой работает только обычный
sRGB/RGBA8 для HTML/Offscreen Canvas. Остальные возвращают `NotReadableError`.
Это **дефект совместимости**, а не успешная защита и не утечка исходных пикселей.
[Отрицательный результат](../native/drafts/environment/canvas-formats70-observations.json).

| Новый прогон | Подтверждено | Ограничение |
| --- | --- | --- |
| Два защищённых профиля одновременно | **6/6** контрольных фаз: оба открыты, закрытие соседа, перезапуск каждого; Canvas/WebGL/Audio стабильны | Windows desktop; не длительный ресурсный тест |
| Mobile Web с тремя модулями | **18/18** фаз, baseline + 8 профилей, оба AudioMath selector; 390×844, DPR 3, touch | Windows с веб-эмуляцией, **не Android/iOS**; обычный sRGB/RGBA8 |
| Полный Python-повтор `bd82e73` | **4405 passed, 1 skipped**, source/status guards прошли | До новых concurrent/mobile/format diagnostics; не нативная пересборка |

[Конкурентный запуск](../native/drafts/environment/combined-concurrent70-observations.json),
[Mobile Web](../native/drafts/environment/combined-mobile70-observations.json),
[Python](../native/drafts/environment/canonical-python70-combined-math-observations.json).

Следующий связанный нативный пакет: формат-сохраняющая обработка P3/F16,
согласованность readback/crop/export и подготовленная коррекция orientation/visibility.
[Контракт исправления](../native/drafts/environment/CANVAS_FORMATS.md).
Подготовлен [изолированный нативный черновик](../native/drafts/environment/canvas-formats-next/README.md):
сохранение P3/F16 и адаптивный шаг вместо теряющегося при RGBA8 одного LSB.
Пройдены 12 transform-проверок со всеми 65 536 half-кодировками и **283 проверки
нативного Skia copy/projection**: четыре пары sRGB/P3, 32 ключа сохраняют разные
F16/RGBA8 результаты на тестовом изображении; проверены отдельные HDR/crop/alpha случаи.
Это **не исправление в браузере** и не 32 настоящих профиля: export/workers/runtime
и широкая HDR-совместимость ещё открыты. Полный Python-повтор `4400f45`:
**4446 passed, 1 skipped**, до адаптивного варианта. Затем — совместный BFCache,
WebGPU, качество Audio, ресурсы, security rebase и доставка/откат.
Основные настройки, допуск production и проверенный бинарник не менялись.
Разделы ниже сохраняют исторические границы прежних прогонов.

## Совместный Canvas / WebGL / AudioMath: первый Windows gate прошёл

| Проверка | Подтверждено | Граница |
| --- | --- | --- |
| Все три модуля включены вместе | 8 защищённых профилей + baseline, **18 initial/restart фаз** | Последовательные профили, пока не конкурентный запуск |
| Canvas и WebGL readback | Согласованность чтения/экспорта, контекстов и перезапуска; межпрофильная изоляция | Не полная защита WebGPU и не антибот-оценка |
| Audio | 5 документов × 54 коротких fidelity-case в каждой фазе; analyser/worklet/realtime controls | Не полная перцептивная оценка качества |
| Реальный эффект AudioMath | Длинный compressor совпадает с baseline для selector 0, отличается для selector 1; стабилен во всех документах и после перезапуска | Два экспериментальных backend, **не восемь Audio-идентичностей** |
| Первый parser script и initial about:blank | Canvas/Audio соответствуют установившемуся документу | WebGL на первом parser script ещё не включён в этот gate |
| Жизненный цикл | Ключи стабильны, наблюдаемые процессы завершены; source/core/receipt guards прошли | Не длительный leak/peak-RAM тест |

[Исходник и измерения](../native/drafts/environment/combined-math70-observations.json).
Полный Python-повтор `9ca759a`: **4379 passed, 1 skipped**, до нового collector.
Следующий пакет: конкурентные защищённые профили, Mobile Web/BFCache в сочетании
с поверхностями, оставшиеся WebGPU/quality/resource gates и security rebase.
Основные настройки и допуск production не изменены.

## Python+JS доставляются вместе в экспериментальный Windows EXE

| Проверка | Результат | Ограничение |
| --- | --- | --- |
| Совместная упаковка | 176 закреплённых файлов, Python-модуль и JS включаются по явному manifest | Старая JS-only схема тоже проходит verify; default не менялся |
| Реальный EXE | Извлечённый `BindingCall.call` совпадает с исправленным кодом, отличается от старого | Проверка содержимого EXE, не полный frozen Native BFCache gate |
| Штатный Native runtime | **18/18** с новым пакетом; исходники и установленный драйвер не изменились | Основной BFCache по-прежнему выключен |
| Recorder → replay | **4/4** desktop/mobile initial/restart | Экспериментальная копия приложения с явным opt-in |
| Гонки восстановления | **6/6**; ещё четыре строгих cancelled-stop случая без loop-ошибок | Barrier только в отдельном тестовом драйвере; не все точки отмены |
| Camoufox / CloakBrowser | Транспортные и frozen Python launch/imports/timeout проверки прошли | Не fingerprint-оценка и не новая поддержка Cloak Recorder |

[Измерения и хеши](../native/drafts/environment/python-js-stage70-observations.json),
[команды сборки](../native/BUILDING.md#experimental-desktop-driver-staging-not-a-chromium-build).
Полная регрессия предыдущего `0770c2e`: **4366 passed, 1 skipped**;
она предшествует новой интеграции упаковки. Далее — общий повтор, совместные
Canvas/GPU/Audio проверки, ресурсы и оставшиеся lifecycle/release gates.

## Полный повтор staging прошёл; закрытие с pending binding проверено отдельно

- **4364 passed, 1 skipped** на `766d9b4`, исходники и статус не менялись во время
  [полного прогона](../native/drafts/environment/canonical-python70-stage-observations.json).
- Новый staged-драйвер действительно прошёл **32 BFCache-цикла / 224 вызова**:
  [свежий прогон](../native/drafts/environment/staged-stress70-observations.json), не перенос старого результата.
- Строгий парный тест закрытия обнаружил **3 необработанных исключения** старого
  Python BindingCall. Черновик исправления прошёл восемь BFCache-циклов и четыре
  отменённых закрытия без loop-ошибок; ключ/storage, владение профилем и завершение
  наблюдаемых процессов проверены. [Пара FAIL/PASS](../native/drafts/environment/binding-close70-observations.json).

Python-исправление пока отдельный черновик, **в desktop-stage не включено**.
Следующий связанный пакет: проверяемая доставка Python+JS вместе, повтор legacy/frozen
интеграции и отмена на других стадиях закрытия. Точечные замеры памяти не считаются
доказательством отсутствия утечек или полной проверкой ресурсов.

## Новый пакет: явный opt-in и проверяемая упаковка драйвера

| Направление | Подтверждено | Граница |
| --- | --- | --- |
| Изолированный staging Playwright | 176 файлов, закреплённые JS/Node, лицензии сохранены; `.venv` не изменяется | Контроль целостности, не подпись релиза |
| Явное включение совместимости BFCache | 30 модельных проверок; штатный Native baseline **18/18** | Основной менеджер по-прежнему отключает BFCache |
| Recorder → replay с новым драйвером | **4/4**, desktop/mobile, initial/restart, настоящий BFCache | Экспериментальная копия приложения, не основной запуск |
| Camoufox и CloakBrowser | Парные original/staged проверки форм, iframe, binding и пяти хранилищ прошли | Не новая поддержка Recorder для CloakBrowser |
| Собранный Windows desktop EXE | Оба движка прошли packaged Python launch/imports и ожидаемый timeout | Не frozen Native BFCache и не Chromium-пересборка |
| Полная регрессия `87f74ea` | **4334 passed, 1 skipped** | Исторический прогон до нового staging-кода |

[Измерения](../native/drafts/environment/driver-stage70-observations.json),
[воспроизводимая сборка](../native/BUILDING.md#experimental-desktop-driver-staging-not-a-chromium-build).
Пакет остаётся экспериментальным: дальше отмена teardown под BFCache-нагрузкой,
контроль ресурсов и frozen Native-интеграция. Полный объём Canvas/GPU/Audio,
генерации согласованных профилей, security rebase и доставки/отката не закрыт.
Разделы ниже сохраняют историю измерений и прежние отрицательные результаты.

## Текущий итог: реальные гонки и полный повтор прошли

| Проверка | Подтверждено | Не означает |
| --- | --- | --- |
| Переход / закрытие вкладки / закрытие runtime при удержанном ответе | **6/6**, desktop/mobile; профиль восстанавливает ключ и storage, наблюдаемые процессы завершаются | Не проверка всех вариантов отмены и аварий под нагрузкой |
| Драйвер без дополнительной инструментализации | **32 BFCache-цикла / 224 вызова handler**, ответы возвращены нужным контекстам без повторного вызова Python | Не peak-RAM benchmark и не полный fingerprint gate |
| Полная регрессия `f99957d` | **4330 passed, 1 skipped**, source/status guards прошли | Не допуск тестового драйвера или релиза |

[Исходники runner'ов и измерения](../native/drafts/environment/bfcache-races70-observations.json),
[полный Python-повтор](../native/drafts/environment/canonical-python70-replies-observations.json).
Основное приложение по-прежнему использует прежний драйвер и отключённый BFCache.
Следующий пакет — закреплённый staging-драйвер с явным opt-in без изменения `.venv`,
совместимость старых движков, отмена teardown под BFCache-нагрузкой и проверка ресурсов.
Свежий upstream audit сохраняет `behind-stable`; security rebase до публикации обязателен.
Canvas/GPU/Audio вместе, генерация проверенных профилей и доставка/откат остаются в полном объёме цели.

## Полный history Recorder → replay: черновик прошёл 4/4

[Публичный runner и пакет ответов binding](../native/drafts/environment/binding-replies70-observations.json)
прошли четыре фазы desktop/mobile initial/restart на неизменённом 001–070:
запись до первого перехода, настоящий BFCache, шесть документов, **все 13 шагов / 9 кликов**
воспроизведены штатным ScenarioExecutor. Pending пусты, предупреждений flush нет.
Дополнительно: **25 модельных контролей** и **18/18 штатных runtime-проверок** с этим драйвером.

Python-handler не запускается повторно: сохраняется только его ответ до восстановления
того же уникального контекста. Исправлена также модельная гонка позднего завершения старого RPC.
Основной драйвер и BFCache-default **не заменены**. Шесть конкретных гонок проверены позднее
в разделе выше; отмена под нагрузкой, закреплённый пакет и ограничения ресурсов остаются открытыми.

Полная Python-регрессия `46c3b4d`: **4325 passed, 2 failed, 1 skipped**;
две проверки старых исходников Recorder переведены на обратную реконструкцию через patch.
Отрицательный полный результат сохранён, полный повтор обязателен. Combined Canvas/GPU/Audio,
проверенные генераторы профилей, security rebase и доставка/откат не объявлены завершёнными.

## Исправление Recorder в основном приложении

`document.open()` удаляет обработчики, даже если `document` и `window` не заменены.
Recorder теперь переустанавливает обработчики через `AbortController`, не дублирует
события и сохраняет незавершённые отправки того же документа.
[Парный контроль](../native/drafts/environment/recorder-document-open70-observations.json):
старый код **5/6 кликов**, новый **6/6 + replay**; свежая штатная runtime-регрессия **18/18**.
Контроль шести frame — desktop; это не проверка всех платформ и режимов.

Полная запись с BFCache пока **FAIL**: все девять кликов получены, но ответ одного
binding главного документа остаётся pending и штатная остановка честно выдаёт предупреждение.
Не удалять ожидание/предупреждение ради PASS. Следующий пакет — доставка результата binding
после восстановления контекста, затем полный history replay и реальные гонки перехода/закрытия.
Главный драйвер и BFCache-default не изменены; остальные fingerprint/package gates остаются открытыми.

## Следующий связанный пакет: восстановление всех сессий Playwright

Черновик [multisession BFCache](../native/drafts/environment/binding-driver70-multisession-observations.json)
на том же 001–070 прошёл **4/4 фазы desktop/mobile initial/restart**: шесть документов,
семь записанных кликов, правильная цепочка селекторов вложенного cross-process iframe.
Дополнительно прошли **13 модельных контролей** и **18/18 штатных runtime-проверок** с новым драйвером.
Проверки обычного Recorder → replay и история BFCache пока отдельные: полный записанный
history-сценарий с начальной навигацией ещё не воспроизведён.

Причина исправления: `Page.getFrameTree` главной сессии не включает удалённые iframe.
Нужно сначала дождаться снимка главной сессии, затем собрать деревья актуальных OOPIF,
проверить поколения/владельцев/родителей и только после этого восстановить frame и контексты.
Драйвер и launch-policy основного приложения **не изменены**. Следующий gate — запись
до первого перехода → настоящий BFCache → все frame → воспроизведение всего черновика,
плюс реальные быстрые переходы/закрытие во время восстановления. Далее — combined fingerprint и доставка пакета.

## Текущий итог 001–070: нативные тесты завершены, BFCache ещё не допускается

| Направление | Подтверждено | Дальше |
| --- | --- | --- |
| Нативные тесты Windows | **484 теста, 20 групп**, итоговые guards и 212 входных хешей прошли | Это не допуск совместно включённых Canvas/GPU/Audio |
| Python-регрессия `2a59a24` | **4320 passed, 1 skipped** | Не подменять результат реального браузера зелёными проверками отчётов |
| Потеря Recorder после history | Chromium доставил binding; Playwright отбросил два контекста до регистрации frame | Восстанавливать дерево и контексты всех OOPIF-сессий, не патчить V8 без доказанной причины |
| Черновик драйвера на D: | Главный документ: 4/4; полное дерево: **FAIL**, отсутствуют `same` и `nested-return` | Проверить все шесть frame, trusted input, полный UI-started Recorder → replay, отмену и закрытие; пока не включать |

Доказательства: [нативный batch](../native/drafts/upstream-156/native-batch70-observations.json),
[диагноз](../native/drafts/environment/binding-driver70-diagnosis.json),
[черновик и сохранённый отрицательный результат](../native/drafts/environment/binding-driver70-prototype-observations.json).
После связанного пакета совместимости остаются combined fingerprint-прогоны, генерация проверенных профилей,
security rebase и установка/обновление/откат. Полный объём цели не сокращён; Linux/macOS отложены.

## BFCache: owner-aware прогон прошёл, повтор Recorder выявил блокер

| Проверка на сохранённом 001–070 | Результат | Граница |
| --- | --- | --- |
| Изолированный launch-overlay без driver-disable BFCache | **4/4 фазы** desktop/mobile initial/restart; настоящий BFCache, по шесть документов до и после штатного снимка | [Эксперимент](../native/drafts/environment/managed-bfcache-optin70-observations.json); патч не применён в менеджере |
| Штатный screenshot owner | Desktop **1366×768**, Mobile Web **1170×2532**; snapshot всех iframe не меняется от снимка | Используется `Page.screenshot` существующего владельца, не чужой EmulationHandler |
| Отдельная CDP-сессия | Mobile PNG **390×844** и до, и после history; воспроизведено и на stock156 | Не доказательство потери DPR от BFCache и не причина менять движок под ошибочное сравнение API |
| Полный baseline на source-overlay приложения | **18/18** existing runtime checks; исходные и overlay-файлы остались неизменными | Не запись history-specific сценария и не protected-policy/release admission |
| Повтор Recorder через BFCache | **3/4**, затем **2/4** с bridge trace; trusted DOM-click не всегда попадает в Python, без warning, при активных JS-маркерах | [Сохранённый FAIL](../native/drafts/environment/managed-bfcache-recorder70-observations.json); блокирует интеграцию BFCache |

В парном screen/CSS-прогоне по **168 snapshots** на runtime: 88 совпали,
80 различались; это сравнение конкретной конфигурации Glint/stock, **не антибот-рейтинг**.
Вначале Recorder-calibration прошла, повтор не прошёл; успешный первый запуск не
заменяет отрицательный результат. Replay полного UI-started draft ещё не проверен.
Следующий шаг — локализовать потерю Recorder-event с трассировкой bridge/JS-state,
без увеличения таймаутов и без включения BFCache в production. Текущий manager-default
остаётся прежним. Параллельная C++-сборка 20 групп не прерывается.
На stock156 та же Recorder/driver-конфигурация потеряла post-click в **4/4**
трассированных фазах. Это не наблюдение, уникальное для Glint; интеграционный
блокер всё равно остаётся нашим обязательным gate.
Дополнительная диагностика: Recorder DOM-listener сохранён в **4/4** фазах,
но пустой binding-ping дошёл до Python только в **1/4**, в трёх — timeout без
входа в bridge. Далее исследуется восстановление Runtime binding/session после
BFCache; точная причина в реализации и исправление пока не заявляются.

## 001–070 собран: первый screen/DPR-прогон прошёл, расширенный lifecycle ещё нет

| Проверка | Фактический результат | Дальше |
| --- | --- | --- |
| Windows build 001–070 | **52 шага, j4, 17м02,68с**; 269 файлов runtime сохранены отдельно с хешами | [Сборка](../native/drafts/upstream-156/build70-observations.json); не release admission |
| Первый скрипт / iframe / перезапуск | **6/6 фаз**, по шесть документов; Mobile Web DPR **3** при первом и повторном чтении | [Результаты](../native/drafts/environment/screen70-first-script-observations.json); исправление main-root подтверждено в этом сценарии |
| Полный baseline NativeRuntime | **18/18 проверок**: изоляция, permissions, owned proxy, сценарии/Recorder, backup/restore, shutdown/cancellation/crash recovery; три раунда по три профиля, остаточных процессов **0** | [Результаты](../native/drafts/upstream-156/runtime-baseline70-observations.json); fingerprint-политики выключены, installed package и cloud team isolation не проверены |
| Реальный менеджер без resize / дополнительных metrics | **144 снимка** screen/CSS/embedding согласованы: две вкладки, навигация, закрытие соседа, initial/restart desktop/mobile | [История](../native/drafts/environment/managed-history70-observations.json); BFCache-gate **FAIL**: флаг драйвера отключает BFCache во всех четырёх фазах, подтверждено `chrome://version` и CDP reasons |
| Полный Python suite на 748e0f5 | **4274 passed, 1 skipped**, 689,171с; source guards прошли | [Полный прогон](../native/drafts/environment/canonical-python70-observations.json); не выполнение нативных C++-кейсов |
| Две вкладки через менеджер | **4/20** строгих fixed-screen стадий; resize меняет screen вместе с viewport по контракту Playwright | [Сохранённый FAIL](../native/drafts/environment/manager-screen70-observations.json); не подменять провал PASS |
| Дополнительный CDP / BFCache | Полный stress **FAIL**, настоящий BFCache и `persisted` всех шести документов подтверждены; остаются screenshot/peer-state и cached-orientation расхождения | [Результаты](../native/drafts/environment/screen-lifecycle70-observations.json) |
| Ввод / снимок после BFCache | Main trusted click и PNG **1170×2532** при DPR 3 прошли; экран не изменился от ввода | [Узкий результат](../native/drafts/environment/history-interaction70-observations.json); ввод во всех iframe и весь lifecycle не подтверждены; ранний navigation timeout сохранён |

Следующий связанный пакет: обновление cached orientation при смене типа без смены угла,
уведомления main-root при обновлении/сбросе logical screen и четыре нативных регрессии.
[Черновик](../native/drafts/environment/orientation-visibility71-preparation.json)
прошёл apply-check на 001–070, **не выбран в manifest и не проверен бинарником**.
Текущие 20 групп C++ собираются отдельно на j4; активные исходники не изменяются.
Для следующего пакета [подготовлен gate `screen-orientation`](../native/drafts/environment/screen-orientation71-gate-preparation.json):
четыре точных имени кейсов в `blink_unittests`, явный upstream-156 и цепочка 0069/0070/0071;
16 Python-контролей выбора/отклонения прошли. Это будущая 21-я группа, **не выполненные C++-кейсы**;
существующие 20 mappings не меняются. Интеграция — только после завершения активного producer.
После их результата — новый пакет, полный screen/lifecycle-прогон, затем Audio и общий admission.
Отдельно проверить opt-in BFCache в изолированном launch-пакете и совместимость Recorder/history.
Не убирать флаг драйвера в production без этих проверок и не выдавать обычную повторную
загрузку history-entry за восстановление BFCache. Прежний extra-CDP stress и этот
manager-прогон имеют разные условия и не заменяют друг друга.

## Полная регрессия после выбора 0070: пять устаревших тестовых контрактов

На 8bbca7c: **4268 passed, 5 failed, 1 skipped**, tracked-source guards прошли;
QML-гонка больше не воспроизвелась. Все пять сбоев — release-tests: три проверки
текущего manifest ещё ожидали 69, две сравнивали исторические 65/66 batch со
списком, куда уже добавлен `screen-widget`.
Исправлены точные ожидания версии/списков, без изменений package/runtime guards.
Полный release-tools модуль после исправления: **1131 passed, 1 skipped**.
[Сохранённый результат](../native/drafts/environment/canonical-python70-preparation-observations.json).
Новый full-suite PASS ещё не заявляется.

## 0070 выбран: связанный DPR-пакет и gate, следующая сборка запущена

В manifest/checkpoint выбран единый двухфайловый 0070: main-root DPR + семь
Blink-кейсов. Gate `screen-widget` интегрирован в существующий verifier/batch:
теперь 20 групп, требуется точное выполнение всех семи случаев в `blink_unittests`.
[Выбор пакета](../native/drafts/environment/screen70-selection-observations.json).
Сохранённый 001–069 остаётся для отката. Owned producer выполняет настоящие
sync/hooks/patch перед j4 build; не подменяются stage markers и timestamps объектов.
Сборка и C++/runtime-проверки нового пакета ещё не завершены.

После изменения manifest/verifier заново выполнены scoped crash, TLS и большой
WebGL-контроль на сохранённом 001–068; их source bindings обновлены реальными
прогонами, старые raw-отчёты сохранены. Это не проверка бинарника 0070.

## 001–069 собран: desktop first-script прошёл, Mobile main DPR ещё FAIL

**2079 шагов, j4, 1ч47м09.05с**; producer завершился exit 0, source/SDK/core
проверки и receipt прошли. Сохранены 269 runtime-ассетов с проверкой хешей.
[Сборка](../native/drafts/upstream-156/build69-observations.json).
На отдельной копии браузера desktop и native-control прошли initial/restart.
В Mobile cross-origin и nested roots сохраняют DPR 3, но main/same/srcdoc/
about-blank после вложенных roots показывают DPR 1. Это подтверждает необходимость
готового связанного 0070, а не завершение screen-политики.
[Все шесть фаз](../native/drafts/environment/screen69-first-script-observations.json).
Новые C++-кейсы и полный комбинированный допуск ещё не выполнены.

## Полная Python-регрессия: сохранён FAIL, устранена гонка QML-теста

На main b6aa9c5: **4254 passed, 1 failed, 1 skipped**, tracked-source guards
прошли. Причина единственного сбоя — тест открывал настройки по факту записи
в БД, не дожидаясь доставки профиля в публичную QML-модель. При задержке доставки
1500 мс исходный тест воспроизводимо падал, ожидание `getProfile()` проходило.
Исправлен только тест: прежний deadline 3 секунды сохранён, добавлен delayed-case.
Весь QML-модуль после исправления: **9 passed**.
[Доказательства](../native/drafts/environment/canonical-python69-preparation-observations.json).
Полный повтор после исправления ещё не выполнен; зелёный full-suite не заявляется.

Отдельно подтверждены TLS 1.2/1.3 и HTTP/1.1 на собственных HTTPS-фикстурах,
с отклонением чужого ключа сертификата. Использовался один диагностический SPKI,
не менялись системные trust stores; обычная CA-валидация, HTTP/2/3 и подмена TLS
не объявляются проверенными.
[Сетевой контроль](../native/drafts/network/negotiation68-observations.json).

## Большой WebGL readback — проверен 4096×4096

На сохранённом 001–068 прошли четыре фазы: baseline, защищённый A, перезапуск A,
защищённый B. Full CPU/repeat/PBO совпадают; три маленьких crop совпадают с full,
внешние sentinel-байты и GL-state сохранены при viewport 2×2. Профили различаются,
перезапуск стабилен, guards/cleanup прошли.
[Результаты](../native/drafts/next-readback/large-attachment68-observations.json).
64 МиБ — размер caller-буфера, не измерение private/RSS памяти. Тайминги получены
под нагрузкой текущей сборки, без обещаний ускорения. Проверен один document/
OffscreenCanvas/WebGL2; workers, другие GPU API и новый 0069 этим не допускаются.

## Аварийное завершение — проверена сохранённая база 001–068

Переиспользованы существующие runtime-gates: **3 раунда × 2 профиля**, аварийное
завершение отдельного Chromium, работоспособность соседа и восстановление
cookies/localStorage/IndexedDB/CacheStorage/SW после перезапуска. Отдельно прошёл
kill собственного Python-контроллера с выходом его наблюдаемого дерева процессов
и восстановлением пяти хранилищ. Оставшихся принадлежащих тесту процессов нет;
source/core/receipt guards прошли.
[Доказательства](../native/drafts/environment/runtime-crash68-observations.json).
Это восстановление **заранее сохранённого checkpoint**, без privacy-политик:
несохранённые транзакции, новые 0069/0070 и server/team isolation не подтверждены.

## NativeRuntime — реальная изоляция и перезапуск профилей

На сохранённом 001–068 прошли **8 lifecycle-проверок** настоящего `NativeRuntime`:
два одновременных профиля, разные ключи, пустое исходное хранилище, отказ второго
владельца и повторного start, независимость cookies/localStorage при закрытии
соседа, сохранение данных и ключей после обоих перезапусков. Ресурсы освобождены,
source/core/receipt guards прошли. [Доказательства](../native/drafts/environment/runtime-ownership68-observations.json).
**Screen-consistency остаётся FAIL** в 36 снимках документов. Блокировка проверена
двумя владельцами в одном Python-процессе; отдельный процесс, crash recovery,
server/team isolation и включённые privacy-политики этим прогоном не доказаны.

Отдельный последующий [межпроцессный контроль](../native/drafts/environment/runtime-owner-process68-observations.json)
прошёл: другой Python-процесс получил отказ, работающий владелец остался доступен;
после штатного close новый процесс успешно открыл тот же профиль. Ключ сохранился,
оба дочерних процесса освободили ресурсы. Это Windows/current-user и штатная
передача владения, не проверка аварийного восстановления или принудительной разблокировки.

## Следующий связанный пакет — native lifecycle-контракты

После 0070 подготовлены ещё четыре Blink-кейса: смена main DPR, обновление
логического экрана remote-root без изменения физических метрик compositor,
отключение политики с возвратом к native snapshot, независимость remote DPR
от чужого Page inspector state с сохранением zoom/CSS. Вместе с тремя кейсами
0070 — семь подготовленных проверок.
[Патч](../native/drafts/environment/screen-lifecycle-native-tests.patch) и
[подготовка](../native/drafts/environment/screen-lifecycle-native-tests-preparation.json).
Apply-check прошёл в отдельном overlay после 0070; активные исходники 0069
не менялись. В queued-фикстуре 0070 также согласован available rect с экраном.
**C++ ещё не компилировался, кейсы не выполнялись.** События
screen/media/orientation и реальные BFCache/input по-прежнему отдельные gates.

Для следующего применения подготовлен **единый двухфайловый**
[linked-screen70.patch](../native/drafts/environment/linked-screen70.patch):
main DPR + валидная геометрия фикстуры + все семь кейсов.
[Apply-check после точного 001–069 прошёл](../native/drafts/environment/linked-screen70-preparation.json).
Он применяется **вместо двух компонентных черновиков, не поверх них**, только
после завершения активного producer. Новых public headers/IPC-схем в пакете нет;
время реальной следующей сборки ещё не измерено.

Для этого же пакета подготовлена [интеграция gate `screen-widget`](../native/drafts/environment/screen-widget-gate.patch)
в существующий native verifier/batch. Он требует семь точных кейсов, отдельный
`blink_unittests`, явный upstream-156 и зарегистрированные 0069/0070.
[12 Python-контролей прошли](../native/drafts/environment/screen-widget-gate-preparation.json),
включая отказ неполным/ошибочным результатам и цепочке без 0070. Это черновик:
активный batch по-прежнему содержит 19 групп; после интеграции будет 20.
Скрипт активного producer не менялся, нативные кейсы ещё не выполнялись.

## Штатный путь настроек менеджера — проверен отдельно

Одинаковый прогон Glint 001–068 и stock156 использует настоящие
`NativeConfiguration.context_options()` / `launch_arguments()`, без дополнительных
page-CDP-сессий: desktop/mobile-web, две вкладки, изменение viewport, переход,
закрытие соседней вкладки и перезапуск persistent-профиля. **216 замеров
screen/viewport/CSS совпали**, оба браузера не прошли строгую проверку устойчивой
идентичности. [Результаты](../native/drafts/environment/manager-screen68-calibration-observations.json).

Таким образом, расхождения исходного baseline не ограничены смешанным CDP-контроллером.
Это не доказательство специфического бага Glint: `set_viewport_size()` может менять
screen по контракту Playwright. Отдельно воспроизводятся исходный экран cross-origin
iframe и Mobile DPR. Следующий допуск — actual 0069/0070 и такой же повторный прогон.
Клики, скриншоты и touch записаны; полный `NativeRuntime`, BFCache и PID-level swap
этим новым прогоном не проверяются. Активная сборка не изменена.

## Lifecycle-калибровка — не путать движок и контроллер автоматизации

На сохранённом 001–068 и официальном stock156 выполнен одинаковый семиэтапный
стресс: две страницы, разные CDP-метрики, обновление/отключение, cross-site
переход и BFCache. **Все 78 замеров screen/viewport/CSS совпали**, включая
одинаковые ошибки ожидаемого состояния. Они не объявляются специфическими
багами Glint: здесь дополнительные CDP-сессии работают рядом с Playwright.
[Парная калибровка](../native/drafts/environment/screen-lifecycle68-calibration-observations.json).

В обоих браузерах подтверждено реальное восстановление **шести документов**:
нативный CDP-event и `pageshow.persisted`, а не обычный reload. Первоначальный
timeout неподдерживаемого Playwright `go_back()` сохранён; проверка переведена
на CDP и сообщения от собственных страниц без замены браузерных API.

Следующий контроль был выполнен отдельно выше: `context_options`, один владелец
настроек, вкладки одного профиля и поддерживаемое изменение viewport.
Отдельно остаются linked 0069/0070, PID-level process swap, графика/ввод
после восстановления и комбинированные защищённые поверхности. Совпадение со
stock в этом узком прогоне не означает полной готовности fingerprint-подмены.

## Вложенные local roots — дополнительный DPR-дефект и черновик 0070

First-script диагностика сохранённого 001–068 выявила: в Mobile Web основной
документ начинает с DPR **3**, после создания вложенных local roots показывает
**1**. Вложенные cross-origin документы также раскрывают исходный экран.
[Полный baseline](../native/drafts/environment/screen68-first-script-complete-observations.json)
завершил шесть фаз по шесть документов: оба native-control прошли, четыре
desktop/mobile фазы воспроизвели дефекты. Trusted-клики и размеры скриншотов
корректны. Начальные незавершённые попытки сохранены отдельно; исправлялись
только экранирование HTML и геометрия тестовой страницы, не опции браузера или
дедлайны. Это проверка сохранённого 001–068, не результат 0069.

В отдельном D: overlay подготовлен [0070](../native/drafts/environment/main-dpr70.patch):
логический DPR применяется и к основному root, не только к подфреймам; добавлены
три Blink simulation-кейса на чужое Page inspector state, zoom/CSS и отключение.
Apply-check на уже применённый 001–069 прошёл без изменения активных исходников.
**0070 не выбран, не скомпилирован и не проверен в браузере.** Входы текущей
сборки 0069 заморожены; последующая проверка должна включать исправление основного
root, а не объявлять завершённым только наследование параметров дочерними окнами.

## Пакет screen/DPR 0069 — историческая подготовка перед сборкой

Подготовлен связанный [черновик из 19 файлов](../native/drafts/environment/screen-inheritance69.patch):
browser-owned логический экран, nullable IPC, widget-scoped DOM/CSS и DPR,
общий расчёт с main-frame emulation, обновление/отключение и события.
Физические данные compositor/input остаются отдельными; JS-подмен нет.
Добавлены **9 C++-кейсов**, но они ещё не выполнены.

Apply-check на неизменённые исходники 001–068 прошёл; официальный Mojom parser
и генераторы typed native/Blink/shared C++ bindings прошли в отдельном каталоге.
[Подготовительные проверки](../native/drafts/environment/screen-inheritance69-preparation.json).
Manifest и checkpoint теперь содержат **001–069**; исходный подготовительный
отчёт сохранён как исторический снимок до выбора патча. В native batch добавлен
отдельный gate `screen-metrics`, требующий все девять случаев в
`blink_common_unittests`; общий список теперь содержит **19** групп.
Runtime 001–068 сохранён отдельно на D: с проверкой всех **269 файлов**.
В этом подготовительном срезе C++/runtime ещё не проверялись; актуальные
результаты сборки и частичного browser gate приведены выше.
Следующий допуск: native-кейсы и реальный браузер — первый script, вложенные
iframe, смена процесса/BFCache, zoom, отключение политики, скриншоты и ввод.

## Пакет 0068 — браузер собран, 18/18 native-наборов прошли

В manifest добавлен fixture-only патч: независимый float seed `10`, проверки
готовности реального Document и негативный тест дублирующихся surface seeds.
Обязательный AudioMath gate расширен с 11 до **12** случаев, без исключений.
Production DSP и защитные проверки не изменены. Python-проверки пакета:
**1252 passed, 1 skipped**; это не результат C++ или браузерного прогона 0068.
Runtime 001–067 сохранён отдельно на D: с проверкой всех 269 файлов.
Реальные sync/hooks/replay и сборка браузера завершены, source/core/receipt
postguards пройдены. GN: 4 мин 39 с; Ninja: 7 мин 04 с, **одно действие**,
97 225 переиспользованных/пропущенных шагов. Хеши браузерного ядра остались
равны 001–067: патч меняет только fixture, не production DSP.
Первый контроллер остановился до компиляции из-за CRLF в изолированном эталоне;
независимый LF replay подтвердил точное совпадение. Неудачный отчёт сохранён.
[Доказательства сборки](../native/drafts/upstream-156/build68-observations.json).
Общий native-прогон завершён: **18/18 наборов прошли**, включая **12/12
AudioMath**. Source/SDK/core/receipt postguards пройдены. Фильтры наборов
пересекаются: их количества нельзя суммировать как независимые тесты.
[Результаты native gate](../native/drafts/upstream-156/native-batch68-observations.json).
Это подтверждает исправление fixture, но не совместимость всех Audio-профилей,
правдоподобие отпечатка или готовность браузера к production.

В main добавлен многопрофильный Audio-прогон с фиксированным количеством
профилей, проверкой точного ключа и Math после перезапуска. Полная изолированная
Python-регрессия: **4138 passed, 1 skipped**; после переноса в main дополнительно
прошли **210** целевых проверок. Это проверка инструмента, не результат
многопрофильного Glint-прогона и не подтверждение реальных device cohorts.

**Фактический Glint-прогон 0068 завершён: 8/8 профилей**, каждый — baseline,
Math и Math после перезапуска. Во всех 24 фазах прошли fidelity 54/54,
analyser 12/12, worklet 12/12 и realtime; ресурсы закрыты, postguards пройдены.
Оба расчётных селектора представлены, ключи сохранены, повторные чтения точны.
[Многопрофильный отчёт](../native/drafts/upstream-156/audio-profile-matrix68-observations.json).
Первый запуск был прерван без отчёта: его каталог сохранён, результата ему
не присвоено. Завершённый прогон использовал новое фиксированное множество.

Все 54 коротких графа совпали с baseline даже у selector 1. Поэтому отдельно
выполнен **длинный compressor-прогон на тех же восьми профилях и ключах**:
15 кейсов × 3 повтора × 3 фазы × 8 профилей = **1080 захватов**.
У пяти профилей selector 1 изменились `random-default`, `constant-compressed`
и `ratio-one`; результаты всех 15 кейсов совпали с float32-прототипом.
У трёх selector 0 изменений нет. Перезапуск побитно стабилен во всех случаях;
identity-файлы, core, receipt и входы не изменились во время измерения.
[Доказательства эффекта](../native/drafts/upstream-156/audio-compressor-effect68-observations.json).

Это **два класса Audio-результатов, не восемь уникальных отпечатков**.
Короткая fidelity-проверка оказалась неразличающей, а не доказательством
неработающей политики. Прямая трассировка внутренней DSP-ветки, реальные
device cohorts и согласованность всех защищённых контекстов ещё не подтверждены;
Math не получает production-допуск из этих измерений.

## Пакет 0067 — 17 native-наборов прошли, AudioMath gate провален

В пакете 0067 добавлен AudioMath: неизменяемая политика OfflineAudioContext,
11 обязательных нативных проверок контекста/ошибок/lifetime и отключённый по
умолчанию эксперимент. GN-рецепт переключён на реальный Git stamp. Windows-сборка
**001–067 завершена: 1 ч 28 мин 46,46 с, 1966 действий, j4**. Source/toolchain
postguards пройдены, записан новый receipt; checkpoint 001–067 сохранён отдельно.
Реальный CDP stamp подтверждён четырьмя GPU-фазами; AudioMath проверен в браузере
только на одном профиле, без доказанного покрытия обоих backend. Raw 001–067
прошёл все **8 существующих runtime-gates / 160 проверок** с source/core/receipt
postguards. Последний проверенный установленный пакет остаётся **001–066**;
новый бинарник не допущен к релизу.

Общий native-прогон завершён: **17/18 наборов прошли**, source/SDK/core/receipt
postguards сохранены. Сборка тестовых бинарников: 1 ч 20 мин 44,41 с, 726 действий.
AudioMath-процесс упал: fixture Audio seed `3` совпадает с WebGPU seed `3`,
политика корректно отклонена, последующий `ASSERT_NO_EXCEPTION` аварийно завершил
набор. Подготовлен незарегистрированный fixture-only ремонт: валидный float seed
`10`, проверка фактической readiness и отдельный отказ для коллизии; плановый gate
становится 12-кейсовым. Он ещё не собран и не выполнен. Защита не ослаблена.

Audio/GPU текущего бинарника проверены с сохранением провала native-gate:
baseline и Math прошли fidelity 54/54, analyser 12/12, worklet 12/12 и realtime
11/11. На этом ключе Legacy прошёл только 24/54 fidelity, 0/12 analyser и
0/12 worklet; realtime прошёл. Общий Audio-результат **FAILED**, ошибки не скрыты.
Math-хеши совпали с baseline: Float32 runtime и обе ветки ещё не доказаны.
GPU metadata off/on и restart прошли по 8/8 WebGL1/2/WebGPU-контекстов; это не
WebGPU readback-защита и не аппаратная когорта. Перед новой сборкой остаются
защищённые identity/worker/combined прогоны; затем регистрируем связанный пакет правок.
Обычный raw runtime-suite уже прошёл 160/160: lifecycle 18, hardware 9, WebRTC 7,
automation 55, fonts 42, identity 18, CDP 6 и combined 5. Это не полный допуск
Math/Canvas/GPU и не проверка установленного пакета.
Далее — полный повтор, согласованность поверхностей и установленный пакет. **12 ошибок Audio-v1 из 54
не объявлены исправленными.** WebGPU, аппаратные когорты и релизный допуск открыты.

В main перенесены ownership-bound монитор ресурсов и повторяемые Audio/GPU CLI.
Stock156 калибровка GPU прошла во всех восьми контекстах и после перезапуска;
это проверка инструмента, не результата Glint. Первый новый Python-прогон сохранил
**4041 passed / 1 failed / 1 skipped**: секундный setup-barrier теста отмены
не выдержал задержки сохранения профиля. Контроль с задержкой 1,2 с воспроизвёл
провал; setup-ожидание исправлено без изменения production deadline. Второй
полный прогон сохранил аналогичную ошибку соседнего cleanup-теста. Оба пути
покрыты общей проверкой медленного сохранения: **625 runtime-тестов прошли**.
Канонический повтор в main: **4047 passed, один skipped**, 401,39 с,
source postguards пройдены. Последующий ACL test-fix прошёл **627 runtime-тестов**
и Windows CI: Python/QML, static checks, C++ policy и packaged-engine job.
Изолированный пакет измерений среды прошёл **4110 tests, один skipped**; после
переноса и добавления draft-контроля main прошёл **4111 tests, один skipped**,
source postguards сохранены. Stock156 с настройками
менеджера выявил screen/DPR-расхождение cross-origin iframe; это ещё не результат
Glint и не исправленный дефект. Новые браузерные политики не допущены.

## Python-интеграция и честная граница Audio — 29 октября

В основной код перенесены Windows-защита профилей от downgrade до загрузки
identity/драйвера, сохранение диагностики ошибок и explicit-поддержка 156 в
worker/surface/WebGL CLI. Полная регрессия: **3862 passed, один skipped**.
Реальный dev-пакет собран и установлен отдельно, без активации; **160 проверок
исходного и 160 установленного браузера** прошли до Python-интеграции.
Канонический повтор также завершён: **18 lifecycle**, **60 worker-кейсов**,
**12 фаз / 24 nested Canvas-кейса** в каждом из двух режимов идентичности;
source postguards пройдены. Это не расширяет production/policy-допуск.

Изолированные CLI подтвердили **60 worker-кейсов** и **12 combined-фаз / 24
nested Canvas-кейса**. Но Audio-fidelity показал **54/54 baseline и 42/54
protected**: 12 ошибок identity/half-gain. Audio-v1 не допускается; следующий
нативный пакет должен исправлять обработку сигнала, а не скрывать этот провал
исключением плоских буферов. AudioMath ещё не проверен в браузере; WebGPU и
подтверждённые аппаратные когорты остаются открытыми задачами.

## Пакет GPU 0066 — собран, нативные проверки пройдены

Общий нативный прогон базы 001–065 завершён: **16 из 17 наборов прошли**,
GPU metadata повторил 6 ошибок из 33; исходники, SDK, receipt и browser core
сохранились. Все последующие наборы выполнены, ошибки не скрыты остановкой.
Проверки пересекаются: складывать их количества как независимое покрытие нельзя.

В manifest добавлен 0066: только исправление GPU-fixture и отрицательный тест
отсутствующего texture-query extension, без изменения production GPU-кода.
Канонический gate теперь требует **34 теста**, без пропусков. Предыдущие
измерения остаются привязаны к `checkpoints/001-065.json`, не к новому manifest.
База сохранена, реальные sync/hooks и source replay завершены. Сборка браузера:
**2 мин 32,62 с, одно действие**, без полной перекомпиляции C++; 256 неизменных
исходников сохранили timestamps. Browser core не изменился, новый receipt
подтверждает всю цепочку 001–066. Канонический общий прогон: **17/17 наборов**,
GPU **34/34**, source/SDK/core postguards пройдены. Точный manifest сохранён
в `checkpoints/001-066.json`. Далее — runtime и установленный пакет, затем
защищённые поверхности/worker-host проверки на 156. Допуск политик не расширен.

Это рабочий контракт для следующих этапов, не отчёт о готовых функциях.
Текущий статус всегда подтверждается исходниками, процессами и свежими отчётами.

## Новый рубеж: Chromium 156 слинкован — 29 октября 2026

Windows 156.0.8078.36 / 001–065: `Build Succeeded`, 19 487 шагов за 3:46:37.79.
Постпроверки исходников/SDK завершились успешно; записан `camouflow-build.json`
с хешами chrome.exe, chrome.dll и chrome_elf.dll. Полный policy-suite ещё не проверен;
AudioMath 0068 остаётся отдельным черновиком и в бинарник не входит.

Первая очередь identity остановилась до тестов: общий process guard заблокировал
Ninja из другого проекта. Исправлена область проверки workspace/binary; процессы
с недоступными данными по-прежнему блокируют запуск. Реальные owned-Ninja проверки
подтвердили разрешение чужой области и запрет своей; пользовательские процессы
не останавливались. Python: 1 439 passed, один skipped; отдельные guard cases — 15 passed.
Старые failed-отчёты сохранены; новая связанная очередь запущена.

Свежие результаты: startup прошёл; target identity-keys выполнил 62 C++-теста
с постпроверками. Также прошли identity-contexts (37) и identity-transport (20),
включая postguards; это unit-level проверки, не допуск identity в браузере.
Два расширенных baseline-прогона прошли все 18 проверок:
пять хранилищ, изоляция, permissions, crash/restart, controlled HTTP proxy,
менеджер/сценарии, Recorder и backup/restore. Первый прогон не прошёл из-за
таймаута закрытия; очистка временной папки замаскировала исходную ошибку.
Этот отрицательный результат сохранён и не считается исправленным повторами.
Ещё три serial-прогона по 18 checks прошли во время реально наблюдавшейся
native-сборки: 160.532 / 146.031 / 146.297 с. Использована isolated verifier-копия
с сохранением failed evidence, без DEBUG/повышения timeout. Все 201 вход и core
хеши неизменны; это не performance benchmark и не устранение первого таймаута.

Отдельная матрица: 16 закрытий 148/156 прошли без изменения timeout/forced kill,
1.140–2.703 с. Новый 156 Audio baseline: 15 cases × 3 = 45 bit-exact совпадений
с standalone native156 DSP. Это не runtime AudioMath, не stock156 A/B и не
полная проверка fingerprint-политик. Последующие identity/eight-gate результаты
указаны ниже; remaining-native, installed runtime и rollback остаются обязательными.
Очищенная запись: `native/drafts/upstream-156/windows-runtime-observations.json`.

Брендинг 156 проверен в самом бинарнике: обе группы иконок совпадают с logo.ico,
ProductName EXE/DLL и заголовок chrome://version — Glint. Кеш taskbar/shortcut
этим не проверен. Подготовлен verifier-only фикс сохранения failed-профиля и
исходной ошибки: пять Windows held-file controls и 18 baseline-проверок прошли
на изолированной копии. Канонический verifier не изменён, таймаут браузера не
объявлен исправленным. Применять только после завершения source-bound очередей
с новой фиксацией входов: `native/drafts/runtime-verifier/README.md`.

Также подготовлен Windows per-profile version guard для прямого выбора EXE:
проверка Last Version/PE FileVersion выполняется под owner lock до чтения ключа
и запуска driver. Прошли 22 marker/PE/mocked-launch контроля и один реальный
owned upgrade 148→156: пять хранилищ и private identity сохранились; обратный
выбор 148 заблокирован до открытия профиля, его файлы не изменились.
Точная patched Runtime-копия прошла ещё 18 lifecycle checks, включая manager,
Recorder, backup/restore и отмену запуска; guard действует и в owned child CLI.
Канонический Runtime пока не изменён. Это не общая гарантия миграций/rollback
и не реализация Linux/macOS: `native/drafts/profile-version/README.md`.

Подготовлен read-only Windows resource observer: PID + creation identity,
kernel/user CPU, working set и private commit. Прошли 24 controls, включая
100 чтений без роста handles, ошибки cleanup и один Glint sample семи процессов
с OS parent-chain проверкой. Это ещё не интеграция watchdog, не новый RAM limit
и не performance benchmark; сумма working sets не равна уникальной физической
памяти. Исходники/ограничения: `native/drafts/resources/README.md`.
Добавлен tree reader: два Toolhelp snapshots, проверка parent creation order
и повторная привязка каждой process identity. Прошли 18 Windows controls,
включая injected API/cleanup errors и 100 captures без роста handles; два живых
Glint-дерева (9/8 процессов) не пересекались. Churn/reused PID не превращаются
в нулевой CPU или частичные complete totals. Profile-root authentication,
orphan/lifetime учёт и безопасная интеграция лимитов остаются следующими gates.
Полная desktop Python-регрессия на Windows/offscreen: 3 614 passed, один skipped,
340.52 с; data/temp/cache изолированы на D, source postguards прошли. Это включает
1 096 release-tool cases, а не добавляется к ним; native/runtime admission
по-прежнему определяется отдельными gates, не Python-счётчиком.

Получен точный официальный CfT 156.0.8078.36: generation-pinned ZIP/MD5/PE version
и реальный CDP revision подтвердились. JSON lookup 404 не означал отсутствия
Windows-архива. Новый Glint-off → CfT → Glint-off прогон: 135 captures, 15 cases,
полное побитовое совпадение и стабильный повтор Glint. Float32 prototype не
совпал с тремя различающими cases; его правдоподобность этим не подтверждена.
У Glint CDP revision нулевой из-за штатного non-official GN default, не из-за
повреждённого checkout. Source binding идёт через receipt/core hashes; реальный
stamp подготовлен отдельным GN fragment и проверен isolated header generation,
но не применён к активной сборке. Full policy/device-cohort admission остаётся false.

Очередь прервалась на handoff 1062/1498: старые процессы подтверждённо отсутствуют,
причина/exit codes неизвестны. Все 201 source input и browser cores сохранились;
объекты не удалялись. Восстановлена связанная очередь identity v6 → runtime v13
→ remaining-native v8 → package v6, j4, без activation. Старые отчёты и неполные
Audio-попытки сохранены; новый A/B/A выполнен полностью с нуля.
Публичный `native/drafts/audio-dsp-math-v2/browser_matrix.py` воспроизвёл ещё
135 captures с прежними хешами; пять CLI rejection controls прошли. Dummy
revision требует явного acknowledgement только известного checkpoint; неверный
stock и существующий/неподходящий output не принимаются. A/B/A использует свежие
профили, не доказывает persistent restart. Profile keys/сырые файлы остаются на D.
Output внутри source checkout запрещён; перед запуском требуется idle builder.
Предыдущий navigation timeout при активном linker сохранён как неуспешная
попытка: deadline не увеличен, причина не доказана.
Восстановленная очередь завершила четыре identity-target: 62 keys + 37 contexts
+ 20 transport + 15 handoff = 134 native unit-теста. Handoff проверяет window
surface и inline-script policy в DocumentLoader; полный runtime-допуск отдельно.
Полный owned runtime-suite Chromium 156 прошёл все восемь gates / 160 checks,
включая combined. Хеши каждого отчёта привязаны к бинарнику и receipt в
`native/drafts/upstream-156/runtime-suite-observations.json`. Remaining-native
очередь началась; установленный пакет и полный Canvas/GPU/Audio ещё не допущены.
Подготовлен следующий Audio compatibility gate: девять графов на 44.1/48 kHz,
точные константы/identity/impulse/stereo, повторные и 37-frame segmented reads,
copyFromChannel/copyToChannel и lifecycle. Два stock156 запуска прошли по
54 renders с одинаковыми хешами; четыре fault-injection controls отклонены
ожидаемо. `audio-fidelity-control.js` / `audio-fidelity-observations.json` находятся
в `native/drafts/audio-dsp-math-v2/`. Следующий шаг — эти же fixtures на Glint-off
и protected policy; stock-калибровка не доказывает работу AudioMath 0068.
Очередь v8 прошла keys 43 / contexts 26, затем устаревший delivery guard отверг
Surface Policy, сравнивая итоговый код с первоначальным черновиком. Исправлена
только проверка: полный ordered replay остаётся обязательным до/после тестов,
десять delivery-файлов дополнительно snapshot/hash-bound. Изолированная копия,
идентичная опубликованному исправлению, прошла все 34 native delivery cases;
242 verifier-регрессии прошли. Chromium source/core не менялись. После сохранённого
scoped-compiler отказа v9 проверено idle-состояние и запущены native v10 / package v7.
Канонический delivery-target v10 также прошёл 34 cases с postguards; очередь
перешла к worker-handoff, где четыре native cases уже выполнены.
Полная Python-регрессия `90ab928`: 3619 passed / 1 failed / 1 skipped; QML-тест
не дождался создания диалога. Добавлено bounded ожидание readiness, все восемь
QML-тестов прошли; исходный неуспешный полный прогон сохранён.
Повторная полная Python-регрессия `01cdf4e`: **3621 passed / 1 skipped**,
467.85 с; 201 frozen input и 143 дополнительных входа не изменились.
Следующий независимый сетевой fixture: bounded parser и owned loopback capture
первого TLS ClientHello, без ServerHello/сертификата и без изменений BoringSSL.
Три свежих headless stock156 профиля дали одинаковые selected offers при разных
GREASE/порядке extensions/размере сообщений. Сырые nonce/session/key bytes не
возвращаются. 32 parser/lifecycle/binding теста прошли отдельно от полного прогона.
Далее — matched Glint/stock на том же endpoint, затем успешная negotiation,
HTTP/2 settings/HTTP/3 и proxy/DNS; текущая калибровка этого не доказывает.
GPU metadata target: 27/33 прошли, шесть texture cases упали. Изолированный
diagnostic-объект подтвердил остановку на guard отсутствующего native extension.
Причина — test base намеренно отключает optional extensions; production запрашивает
texture-query extension штатно. Test-only патч запрашивает prerequisite и обновляет
bindings; отдельный отрицательный case сохраняет unavailable без GL-ошибки.
Shadow fixture-object + исходные production libraries прошли **34/34** cases;
patch replay/reverse-check и неизменность checkout/core/201 входа подтверждены.
Патч пока не выбран, canonical gate и package v7 не допускаются. Далее — явно
продвинуть fixture в проверяемую цепочку, завершить worker-surfaces/font targets,
повторить canonical native queue и установленный пакет.
Перед продвижением fixture сохранён byte-identical manifest 001–065:
`native/drafts/upstream-156/checkpoints/001-065.json`. Исторические Audio/GPU
дескрипторы теперь ссылаются на него с прежним SHA-256, а не на изменяемый
`manifest.json`. Все 65 patch-хешей проверены; release-tools регрессия прошла
1105 тестов, один skipped. Текущая selected-цепочка и Chromium checkout не менялись.
Хвост native-проверок завершён: worker-surfaces 55 / font-rasterization 5,
оба с postguards. GPU canonical gate всё ещё остановлен на подготовке fixture.
Добавлен batch CLI: одна Ninja-команда на все нужные EXE, затем каждый точный
фильтр отдельно; ошибки не скрывают последующие targets. Source/core/receipt/GN
и SDK проверяются в общем checkpoint до/после; временные файлы остаются на D.
Single-target API сохранён. Регрессия orchestration/network/evidence: 1165 passed,
1 skipped; дополнительные temp-directory controls — 27 passed. Реальный batch
ещё не допущен; исходный GPU-failure не обходится и не вычёркивается.
Matched ClientHello Glint-off → stock → Glint-off: девять свежих headless профилей,
selected offers совпали; core/source guards и cleanup прошли. Это baseline 001–065,
не negotiation/full packet/HTTP2/HTTP3 и не обещание невидимости.

## Следующий пакет: AudioContext math policy — 29 октября 2026

Подготовлен отдельный draft 0068 для Chromium 156 после 001–065:
режим/error фиксируется const-полем в конструкторе BaseAudioContext,
backend выводится из Audio surface seed через отдельный HMAC-домен,
компрессор получает собственную неизменяемую политику. Math-only путь не смешивается
с v1 readback farbling; отсутствие политики не разрешает возврат сырых данных.

Полный source replay 65+0068 прошёл на 194 pinned inputs; GPU ordinals и GRIT
сохранены. Изолированно скомпилированы шесть production objects и тестовый TU;
одиннадцать C++ fixtures **не слинкованы и не выполнены**. Исправлен найденный компилятором
вызов `destination()` на настоящий C++ API `destinationNode()`, добавлены проверки
backend непосредственно в handler. Полный GN graph и все потребители новых layouts
этой объектной проверкой не подтверждены.
Реальные stock/Glint-off 148: шесть замеров разрешают создание компрессора после
закрытия AudioContext и после удаления iframe с сохранённым OfflineAudioContext.
Последний остаётся `suspended`; удаление frame не равнозначно строке `closed`.
Поэтому lazy-поиск seed заменён фиксацией при создании; добавлены проверки первого
узла после переключения feature, native error precedence, detach и навигации.
Это baseline-наблюдение, не выполнение нового AudioMath в браузере.
Фича выключена по умолчанию, патч не выбран в manifest; 201 frozen input активной
сборки не изменился. Это не runtime-допуск и не готовая модель реальных устройств.

Далее: завершить текущий 156 baseline и связанные проверки; затем отдельно
собрать пакет AudioMath, выполнить fixtures, снять matched-version browser controls,
проверить lifecycle/AudioWorklet/realtime, качество звука и производительность.
См. `native/drafts/audio-dsp-math-v2/context-integration.json` и README workbench.

## Новый результат: Audio-v1 fidelity на Glint 148 — 29 октября 2026

Расчётный риск подтверждён matched-version прогоном: stock Chromium и Glint
148.0.7778.96 использовали одинаковый owned HTTP origin и настройки. Все 12
контрольных замеров stock/Glint policy-off точны; 14 из 24 protected-замеров
меняют один float32-бит. В число входят повторные замеры после перезапуска.
Оба derivation mode проверены на двух новых профилях; identity-restart стабилен,
но стабильность не означает правдоподобность.

Collector завершён без ошибок, compatibility=false. Десять runtime owners
освободили handles; данные профилей, core-файлы, compiled receipt и 201 frozen
input сборки 156 не изменились. Публичный очищенный JSON связан хешем с probe;
приватных ключей и пользовательских данных в нём нет. Это не результат 156/157.

Далее нужен пересмотр Audio-модели для plausible identity: v1 оставлять только
experimental farbling, не принимать вариативность хеша за fidelity. Контроли
констант/identity graphs/segmentation обязательны; flat-buffer shortcut не годится.

## Параллельный пакет: chunked Audio fixtures для 157 — 29 октября 2026

Выявлен отдельный риск fidelity: v1-маскирование для seed 5 меняет даже константу
0.25 на один бит. Контроль stock Chromium 148 реально сохранил точные 0, ±0.25 и
0.5, по 256 samples; это не matched A/B для новых 156/157. HMAC-векторы проверяют
механику v1, но не правдоподобность. Добавлен публичный JS-контроль и явный false
для compatibility/production gate. Перед допуском нужны matched controls и решение
модели Audio без нарушения whole-render/chunk consistency; flat-buffer shortcut
не принимается. Активная сборка и проверенный 148 не менялись.

Подготовлены одиннадцать C++-тестов: missing policy до resolver/thread, приоритет
нативных zero/overflow ошибок, бюджет после округления и retry, маленький chunk
при большой finite length, очередь 128/128/44 с одним финальным событием и общей
mutable event/Promise ссылкой, независимые ненулевые signal vectors двух политик,
flag-off indefinite rendering и закрытие без completion event. Добавлены
protected queue suspend/resume, закрытие очереди на паузе с отклонением обеих
render Promises и будущего suspend, а также приоритет closed-state ошибки.

0066 лежит отдельно от выбранных patches и manifest; текущая цепочка остаётся
001–065. Проверены применение в отдельной копии, пять pinned API headers и
независимые Python HMAC-векторы. **Компиляции и исполнения этих тестов нет.**
Отдельных fixtures пока нет для injected copy-failure cleanup и lifetime при
teardown; все 11 случаев требуют реального прогона 157. Все 201 frozen input сборки 156
неизменны; расширение не выдаётся за runtime/anti-bot PASS.

## Предыдущий этап: сборка 001–065 — 29 октября 2026

Проверенный пакет 0065 включён в manifest и исходники. Повторный keep-going
прогон прошёл для всех 85 production object targets и 38 mapped test TUs;
production-объекты переиспользованы, три исправленных тестовых объекта пересобраны
за 27.34s. Source/toolchain/GN postguards прошли. Sync/hooks не перезапускались:
проверены прежние dependency inputs и перепривязаны записи.

Сборка браузера возобновлена в j4, лог `build-20261029-074910.log` на D.
Очередь: browser continuation v2 → identity v4 → runtime v11 → remaining native v6
→ package v4 (201 source hashes, отдельный store без activation). Реального
результата native/runtime пока нет; исходники, GN и native_build.py заморожены.

Полный source replay 65 патчей прошёл для .36, .75 и Chromium 157. У 157
по-прежнему нет компиляции/runtime; source-only успех не завершает перенос.

## Предыдущий рубеж: исправление native fixtures — 29 октября 2026

Keep-going компиляция 38 выбранных test TUs закончилась за 48m45.34s:
три файла не собрались, postguards прошли. Ошибки: отсутствующий WaitForInit,
новые bool-аргументы worker storage/origin API и unsafe canary indexing в GPU-тесте.
Очередь линковки/native/runtime/package корректно остановилась по ошибке;
браузер из этого запуска не получен. Объекты сохранены.

Следующий связанный пакет исправляет только эти три test TUs. Все три копии
собрались с исходными Clang flags; postguards и git apply --check прошли.
Публичный 0065 пока вне manifest и каталога выбранных patches: требуется явное
включение пакета, перепривязка manifest/source guards и возобновление очереди j4.
Это не пауза цели и не основание объявлять runtime готовым.

## Выполненный source-пакет: Chromium 157 — 29 октября 2026

Полный публичный manifest теперь проходит применение **64 патчей к 185 исходникам**;
сохраняются 321 GPU-команда, добавленный ID 577 и структура GRIT. Это не сборка
Chromium 157 и не подтверждение работы Audio в браузере.

Подготовлен прототип chunked OfflineAudioContext: бюджет фактического размера
чанка до выделения буфера, захват seed/flag-off один раз, обработка результата
до Promise и закрытие с отклонением очереди при ошибке копирования. Сохранены
upstream-очереди, optional total length, финальный completion event и GPU idle-trim tests.
Следом нужны нативные проверки чанков, повторных вызовов, ошибок, suspend/resume
и идентичности финального event/Promise. `complete_forward_port` остаётся false.

Изменения изолированы от активной сборки 156; её исходники, GN и цепочка 001–064
не менялись. Проверены все 200 хешей входов ожидающей упаковки. Реальные бинарник,
native/runtime-тесты и упаковка 156 по-прежнему идут через существующую очередь j4.

## Предыдущий срез: перенос на Chromium 156 — 29 октября 2026

| Направление | Состояние и следующий критерий |
| --- | --- |
| Проверенный пакет | Chromium 148 / 001–062 сохранён; результаты ниже относятся только к нему |
| Текущий portability batch 0064 | После unsafe memcpy в Audio добавлен bounded domain copy без изменения HMAC/float-policy/GN. Все 85 object targets для 83 изменённых production sources прошли с postguards; 65536 byte-layout pairs совпали. Отдельно компилируются 38 test TUs, без исполнения fixtures. Два validating-decoder test-файла исключены текущим GN=false и не считаются покрытыми. Полный браузер возобновляется только после завершения этой связанной проверки |
| Полный корпус 157 | Получены и проверены все 185 inputs через сохранённые Gitiles-данные и верифицированные Git-объекты; полноценного checkout нет. Публично разделены prefix 001–032 (88 inputs, passed source replay) и полная попытка 001–064 (185 inputs, failed на 0033). Следующий порт — chunked OfflineAudioContext: optional total length, budget фактического chunk, неизменный seed и согласованные event/Promise; нельзя отключать upstream chunking ради применения патча |
| Safe-buffer port 0063 | Полная 001–062 сборка остановилась на трёх объектах из-за unsafe-buffer errors, не OOM/диска. Добавлен отдельный 0063: typed ranges в обоих Hardware headers и fixed-size spans в Canvas. Все три объекта финального вида скомпилировались; 24025 parser pairs и 196608 byte-layout pairs совпали. Полная j4-сборка продолжена с сохранёнными объектами; runtime 156 ещё не подтверждён |
| Предыдущий рубеж переноса 157 | Public replay 001–029 прошёл на 72 проверенных inputs после адаптации пяти патчей; остальные 24 payloads переиспользованы. Следующая ограниченная загрузка после cooldown сохранила уже 76 из 185 inputs, затем timeout на document_loader.cc остановил её без retry. Это исторический prefix, не полный перенос; актуальный 001–032 и полный корпус 185 inputs описаны выше. Тогда полный Python suite: 3553 passed, один skipped |
| Получение sparse sources | Добавлен публичный fetch CLI: immutable URL, размер/SHA, read-only cache, запросы раз в две секунды, без retries/redirects. Реальный прогон: 185 cache hits → replay 62 патчей; отдельно один cold HTTPS файл. Это не полный cold download или runtime-допуск. Следующий шаг — завершить текущую сборку и выполнить привязанную очередь проверок |
| Upstream-аудит 29 октября | Официальная Windows Stable metadata содержит 157.0.8103.27 и patch-line 156.0.8078.75. Default 148 и candidate 156.0.8078.36 — behind-stable. Добавлен явный --candidate audit с manifest/patch guards. Текущая сборка остаётся неизменной проверочной базой; следующий upstream target и security review нужны до production, автоматического переключения нет |
| Forward preflight | После cooldown ≥15 минут и перехода на один запрос раз в две секунды для 156.0.8078.75 проверены все 185 inputs и clean replay всех 62 неизменённых патчей; GPU IDs/GRIT invariants прошли. Для 157 получены 28 inputs, затем HTTP 503 остановил job без retry loop. Все 302 active input hashes неизменны. Это source-context replay, не checkout/компиляция; build target не переключён. Первые 429/частичный 001–029 сохранены в матрице |
| Публичный refresh replay | Опубликован manifest 156.0.8078.75 без копий 62 патчей; verifier принимает явные paired manifest/patch-directory. Public CLI прошёл оба default .36 и explicit .75, дерево совпало с прежним private replay, codegen сравнил 30 GPU outputs. 3524 Python tests passed, один skipped; refresh не зарегистрирован как build target. Ожидающие контроллеры обновлены под проверенный source cohort, реальная сборка не перезапускалась |
| Очередь нативной регрессии 156 | После четырёх identity targets и полного runtime suite привязана к живому process handle очередь 13 остальных/default target selections, последовательно j4. Есть перекрытие fixtures; это не 13 новых уникальных наборов и пока не результаты. Ошибка/смена входов/retirement предыдущего контроллера останавливают запуск |
| Очередь доставки 156 | После compile-only fixture batch возобновляется browser build, затем identity v3 → runtime v10 → remaining-native v5 → package v3 с 200 input hashes. Старые цепочки остановились при ошибках без тестов/упаковки. После успешных 13 selections/postguards: staging j4 → архив → отдельный D-store без активации → полный runtime suite установленной копии. Реальные staging/package/install ещё не начались; production и совместимый rollback этим не подтверждены |
| Исходники 156 | Прерванный checkout восстановлен до закреплённого revision; оригиналы несовпадений сохранены. 24 файла объяснены Git text filters, один обрезанный fixture восстановлен из точного blob |
| Зависимости | Sync и hooks завершены в отдельном `D:\Glint156Candidate`; все 62 candidate-патча применены и проверяются вместе с V8 |
| Сборка Windows | Оба unified system module targets прошли после замены VC junction обычной копией. Полный запуск завершился с 19 ошибками отсутствующего `dia2.h` в Dawn DXIL. После добавления установленного DIA SDK реальная `lib_dxildia.lib` собрана, postguards прошли; полная j4-сборка продолжена с сохранёнными объектами. Новый браузер ещё не слинкован |
| Подготовка toolchain | Публичный `scripts/native_windows_toolchain.py` копирует VC, DIA SDK и Windows SDK, проверяет хеши, лимиты и OS lock. DIA headers/libs/runtime входят в проверку дрейфа. Существующие config/output не заменяются; Windows-установка не меняется. Полная повторная подготовка новым скриптом в свежем checkout ещё не проверена |
| Доставка 156 | Staging, packaging и runtime suite принимают явный candidate и проверяют manifest/Chromium/V8 chain, receipt/core и drift. Suite проверяет версию каждого gate и гонки initial measurement; staging удерживает OS lock и проверяет локальный toolchain. Конкурентный staging отклонён настоящей активной сборкой без изменения её состояния. Полный Python suite: 3379 passed, 1 skipped. Реальные staging, архив, установленная копия и rollback 156 ещё не выполнены; policy admission не менялся |
| Нативные тесты 156 | Инструмент принимает явный `--candidate upstream-156`, проверяет revision/manifest/patch chain и исключает одновременную сборку. Сами нативные cases на 156 ещё не выполнены |
| Регрессии 148 | Свежий full suite выявил timeout закрытия контекста; runtime-only повтор прошёл 18/18, затем отдельный stress — 10 раундов по три профиля. Причина timeout не установлена; условия и результаты — в матрице |
| Новые возможности | Canvas/GPU/Audio experiments не получают допуск от успешного переноса исходников или Python-тестов; нужны linked native tests, совместимость и runtime-проверки точного пакета |
| Закрепление окружения профиля | В Browser JSON добавлено явное Pin environment → проверка черновика → Save. Параметры окружения больше не наследуют изменения общих defaults; grants, пути, headers и ключи не копируются. Реальный менеджер на Glint 148: четыре запуска, 36 document-значений, корректное закрытие и неизменный пакет. Это не фиксация всего fingerprint и не проверка 156 |
| Text gamma/contrast | Девять ограниченных пресетов добавлены в UI и JSON; экспериментальный допуск только точного проверенного пакета 148 и Native rasterization. Реальный менеджер: 36 запусков / 288 first-script наблюдений / 36 editing/export прогонов, desktop и Mobile Web. Полный Python-прогон: 3455 passed, один skipped. Это не девять доказанных идентичностей и не допуск 156 |
| Совместимость редактирования | На stock/Glint 148 прошли 36 прогонов: Unicode, undo/redo, выделение, реальный загруженный шрифт, DOM/SVG/Canvas, PNG round trip, UTF-8 download и ограниченная проверка PDF. Дополнительно проверено сочетание с допущенными CPU/RAM/WebRTC и media preferences: четыре прогона, 32 first-script контекста. Это контролируемые страницы, не общий допуск приложений или fingerprint-параметров |
| Параллельные профили | На Glint 148 прошли девять text-tuning конфигураций с двумя запусками и парами одновременно открытых профилей: 144 контекста, 18 editing/export прогонов. Изображения совпали с последовательной базой; пять хранилищ изолированы и сохраняются после перезапуска. Ограничение runner — два профиля; это не лимит продукта и не проверка 156 |
| Восстановление и закрытие | На 148 прошли три раунда с тремя профилями, crash/restart, пятью хранилищами и нулём оставшихся owned processes для одной комбинированной text policy. Добавлен native_close_report: forced cleanup нельзя выдать за штатное закрытие. Все 36 финальных manager closes чистые, но причина timeout в раннем v4 не установлена; исходный сбой сохранён в матрице |
| Диагностика редкого timeout | Дополнительные 24 manager-запуска: minimal против workers/editing/export, три text policy, два профиля и перезапуски. Все 24 завершились штатно, actual child exit 0, оставшихся owned processes нет; закрытие 0,687–13,625 с. Сбой не воспроизведён и не объявлен исправленным; таймауты и fallback не менялись |
| Canvas security/reset | Расширен существующий verifier: clearRect, ImageBitmap propagation, resize/reset, повторный export и re-taint. Stock и Glint 148 совпали в 12 security-контекстах по 22 полям, initial/restart; оба child exit 0. Проверяется feature-off совместимость, не допуск Canvas-защиты. Порядок исключений tainted + zero size отличается от текущего HTML Standard и явно сохранён как измеренный Chromium baseline |
| Комбинация защит с reset-проверками | На сохранённом 148 / 001–062 прошли по 12 фаз для partitioned-privacy и profile-identity: Canvas/Audio/WebGL вместе, concurrent close/restart, missing-policy denial. По 24 nested Canvas cases в каждом режиме; core/receipt/source неизменны. Это не полный runtime suite и не исправление известных raw-pixel/fidelity ограничений; privacy_admitted=false |
| Backup owner exclusion | Исправлен экспорт сессии без Native owner lock: lock удерживается на весь ZIP snapshot, запуск и export взаимно исключаются. Реальный менеджер 148: live export заблокирован, restore сохранил пять хранилищ с новым ключом, исходный профиль сохранил свой ключ и данные. Метаданные не читают browser files; это не key-preserving rollback и не проверка 156 |
| Windows key-file ACL | Подтверждено наследование широких прав старым QSaveFile-путём. Менеджер теперь создаёт приватный файл с ACL до записи, fsync и атомарно публикует его; существующие валидные ключи сохраняют точные байты/seed. ФС без persistent ACLs и ошибки записи блокируют запуск. На одном старом D-fixture grants 2→0, HMAC-результаты неизменны. Это не защита writable parent и не глобальное изменение прав |

После сборки 156: нативные identity/context/transport/handoff tests → полный
runtime suite → совместимость Canvas/Audio/GPU и шрифтов → диагностические сайты.
Пакет и возможность отката проверяются отдельно перед включением политик и релизом.
Команды и ограничения candidate: [upstream-156](../native/drafts/upstream-156/README.md).
Linux/macOS остаются отложенными; мобильный режим — Web Emulation.

## Предыдущий проверенный рубеж: 18 октября 2026, 001–062

- Windows-бинарник собран: j4, 29 мин 02 сек, 52 выполненных шага; это инкрементальная сборка.
- Повторный полный runtime-прогон: **160/160**, все восемь gates. Причина первого
  `NetworkError` в проверке шрифтов не установлена; успешный повтор не считается исправлением.
- Брендинг Glint проверен на этом бинарнике: иконки, ProductName, страница версии.
- Windows text rendering: **5/5 нативных тестов**, шесть конфигураций, два запуска
  каждого профиля, восемь контекстов. Проверены текст, явные пиксели, форматы и HDR.
- CPU/RAM, реальные шрифты, WebRTC routing, webdriver/UA и рендеринг шрифтов
  включаются экспериментально только для проверенного установленного пакета.
  Manifest и все файлы проверяются перед каждым запуском политики; неизвестные
  и изменённые runtime блокируются. Общий допуск форка этим не подтверждается.
- Официальный Windows staging завершён: 8 мин 49 сек, два выполненных шага.
  Полный пакет установлен в отдельный store: 261 файл, архив 220,95 МиБ.
- Установленная копия прошла **160/160** проверок с контролем полного payload.
  Активация 001–010 → 001–062 → откат → 001–062 сохранила пять хранилищ одного
  тестового профиля; пользовательские профили и настройки не переключались.
  Проверена активация версии бинарника, не допуск fingerprint-политик.

Дальше: согласованные профили и совместимость обычных приложений, отдельная
проверка актуальности upstream перед production. Актуальная доказательная
база и ограничения: [матрица тестов](GLINT_TEST_MATRIX.md). Внешние результаты
старых бинарников не переносятся на 001–062. Linux/macOS остаются отложенными.

## Предыдущий проверенный рубеж: 14 октября 2026, 001–059

| Проверка | Фактический результат |
| --- | --- |
| Сборка Windows Chromium | 16 мин 35 сек, j4; receipt всех 59 патчей, отдельная запускаемая копия 001–047 для отката |
| Нативный identity-пакет | 134/134: keys 62, contexts 37, transport 20, Blink handoff 15 |
| Базовый runtime | Все 8 gates, 160 проверок прошли |
| Canvas/Audio/WebGL вместе | Оба режима: profile-identity и partitioned-privacy; каждый 12/12 фаз и 24 nested Canvas cases, включая concurrent/restart |
| GPU metadata | 33/33 нативных cases; расширенный passthrough-прогон 74/74 включает эти 33 |
| Реальные внешние антибот-сервисы | Четыре сайта: BrowserScan Normal, Sannysoft без найденных FAIL; замечания CreepJS и timing-флаг Device and Browser Info остаются; PASS CAPTCHA не заявляется |

Первый combined identity-прогон выявил ошибку конфигурации теста: не включён
GPU metadata transport. После исправления флагов тот же бинарник прошёл оба
режима; не ослаблялись проверки пикселей и не подменялись данные.
Это доказательство работы на контролируемых fixtures, не релизный admission:
дальше повторные прогоны, совместимость, реальные сайты и согласованные профили.
Актуальные доказательства и ограничения: [матрица тестов](GLINT_TEST_MATRIX.md).

Контрольный Chromium той же версии также показал timing-флаг на трёх посещениях
через тот же прокси. Это не ручной baseline: headless/CDP сохранялись. Причина
сигнала не установлена; менять таймеры без изоляции факторов нельзя. Приоритет
следующего пакета — обнаружимость Canvas, совместимость графики и согласованная
идентичность, а не обещание универсального PASS.

Контролируемая проверка Canvas уточнила проблему: текущий readback-кандидат
меняет 720/768 пикселей явной непрозрачной палитры и 667/768 пикселей градиента
(ошибка канала не выше 1). Повторное чтение, PNG и повторная запись согласованы,
но это не точность исходного изображения. Feature-off Glint совпал по метрикам
с обычным Chromium. Следующий дизайн должен учитывать происхождение пикселей
и сохранять явные image-data операции; простое уменьшение процента шума не
заменяет этот контракт. Проверки workers, HDR и цветовых пространств остаются.

Дополнительный API-прогон на отдельной копии 001–059 проверил sRGB/Display-P3
и unorm8/float16 в документе и dedicated worker. Обычный Chromium и feature-off
Glint поддерживают четыре сочетания. Текущая защита вызывает NotReadableError
при чтении и PNG-экспорте трёх сочетаний за пределами sRGB/unorm8: шесть сбоев на контекст.
Это подтверждённый пробел совместимости, не PASS; полноценная HDR-точность ещё
не проверена. Во время сборки 001–060 нельзя исправлять активные исходники:
следующий связанный Canvas-пакет должен сохранить форматы, alpha, цветовые
преобразования, явные ImageData-операции и согласованные экспорт/чтение.

### Следующий Canvas-пакет: направление, не готовая реализация

Сначала отделить правдоподобную идентичность от анти-трекингового изменения
readback. Простое копирование farbling не решает наш контракт: актуальный
[код Brave](https://github.com/brave/brave-core/blob/master/third_party/blink/renderer/core/farbling/brave_session_cache.cc)
выбирает изменяемые RGB-биты на основе HMAC содержимого. Это механизм изменения
пикселей, а не доказательство точности явных ImageData-операций. Исследование
[WWW 2025](https://www.hoangdainguyen.com/publications/canvas_fp_attack_www25.pdf)
показывает восстановление данных при изученных randomization-защитах. Оно не
доказывает уязвимость каждой будущей версии; результат нельзя превращать в
обещание невыявляемости нашего алгоритма.

Наше инженерное решение для следующего прототипа — исследовать изменения
реального рендеринга, согласованные с профилем, вместо произвольной подмены
готовых пикселей. Первое ограниченное направление — нативные Windows font
rasterization-параметры; другие ОС и выдуманные GPU не добавлять. Это гипотеза,
которую ещё нужно реализовать и измерить, не готовый патч и не гарантия.

| Контракт следующего пакета | Проверка перед включением |
| --- | --- |
| Явные пиксели не приобретают искусственный отпечаток | Opaque putImageData/readback, crop, повторная запись; transparent rounding сравнивается с stock |
| Рендеринг действительно изменён, а не только экспорт | Снимок реального canvas, getImageData, PNG, ImageBitmap/drawImage согласованы |
| Профиль согласован | Canvas/DOM/SVG/worker text, метрики и доступные реальные шрифты проверяются вместе |
| Форматы не деградируют | sRGB/Display-P3, unorm8/float16; alpha, HDR-значения и tone mapping отдельно |
| Идентичность сохраняется | Restart/clone/restore и два профиля; никакой смены настройки при каждом чтении |
| Privacy-режим не выдаётся за обычную идентичность | Явно версионированная политика и отдельный admission; старый эксперимент не включается автоматически |

Изолированные черновики и проверки разрешены во время сборки. Зарегистрированные
патчи, активные исходники и GN остаются неизменными до терминального завершения.

## Промпт для продолжения работы

### Уточнение цели: правдоподобная идентичность, а не пустой отпечаток

Основной режим должен сохранять обычное поведение браузера и согласованные
характеристики, а не скрывать все данные. GPU minimization остаётся отдельным
опциональным режимом приватности; отсутствие расширений и пустой renderer
не считаются доказательством правдоподобия.

| Следующий этап | Обязательный результат |
| --- | --- |
| Измеренные эталонные окружения | Версионированные наборы реальных ОС/Chromium/GPU/шрифтов/экранов; источник и условия измерения |
| Согласованный профиль | ОС, UA/Client Hints/HTTP, GPU/limits/extensions, шрифты, экран, Intl/язык/часовой пояс выбираются совместно, не случайными независимыми строками |
| Нативная доставка | Один контракт для документа, iframe и workers; HTTP и JS не противоречат друг другу |
| Жизненный цикл | Идентичность стабильна после restart; clone/restore и partition-политика проверяются отдельно |
| Проверка поведения | Реальные texture/mip/layer/readback, Canvas, Audio и обычные приложения работают; изменение hash не заменяет совместимость |
| Мобильные профили | Пока честная Web Emulation; настоящая Android-oriented идентичность требует отдельного согласованного покрытия, а не только UA/viewport |

Не выдавать вымышленную видеокарту с возможностями другой, не обещать симуляцию
другой ОС или обычного пользователя на любом сайте без фактической проверки.

### Контекст для следующего запуска

> Продолжай разработку Glint — собственного Chromium-движка CamouFlow.
> Сначала прочитай AGENTS.md, native/README.md, native/BUILDING.md,
> native/ARCHITECTURE.md, docs/NATIVE_ENGINE.md, docs/NATIVE_VERIFICATION.md,
> docs/GLINT_TEST_MATRIX.md и этот план. Проверь актуальные Git HEAD, изменения,
> build-lock, применённые патчи, реальный процесс сборки и последние отчёты.
>
> Работай только под Windows. Исходники Chromium, инструменты, кэш, бинарники
> и машинные отчёты держи во внешнем workspace на D:. Не меняй исходники,
> зарегистрированные патчи и GN активной сборки. Не запускай вторую сборку
> в том же output. Не останавливай сборку из-за одного устаревшего лога:
> проверь процесс и фактическую причину. Параллельность — максимум 4;
> если подтверждён OOM, сообщи об этом, прежде чем менять запрошенный режим.
>
> Следуй существующим Python/QML/C++-паттернам. Сохраняй зелёный брендинг.
> Не подменяй Glint сторонним движком и не используй JS monkey-patching,
> framework stealth или отключение безопасности как доказательство защиты.
> Не выдумывай GPU, ОС, версии браузера и результаты CAPTCHA.
>
> Выполняй этапы ниже последовательно. На каждом этапе: воспроизведение,
> минимальное изменение, негативные контроли, проверка конкретного бинарника,
> обновление статуса и таблицы результатов. Подготовленный патч,
> скомпилированный объект и проверенный chrome.exe — разные уровни доказательства.
> Не называй ограниченную проверку полной невидимостью CDP.
> Перед новым модулем откалибруй измеритель на обычном Chrome. Разделяй
> изменения значений, нарушения поведения API и ожидаемые различия контекстов.
> Изменённый hash сам по себе не доказывает защиту или отсутствие связывания.
>
> Используй только публичные диагностические сайты и контролируемые страницы
> без реальных аккаунтов. Прокси и ключи бери из приватной конфигурации;
> никаких прямых сетевых фоллбеков. CAPTCHA оценивай только по фактическому
> результату; тестовые ключи проверяют интеграцию, не реальную антибот-защиту.
> Не применяй платные решатели или подмену токенов.
>
> Проверенные изменения коммить и пушь непосредственно в main, сохраняя чужой
> WIP. Приватный server, секреты, профили, бинарники, сырые fingerprint-отчёты
> и дневники не публикуй. Изменение движка не допускай в production только
> потому, что оно скомпилировалось: нужны capability gates, проверка пакета,
> безопасность upstream и rollback.
>
> В конце каждого этапа кратко сообщай: что изменено, что реально проверено,
> что не проверено/сломано, где доказательства, commit и следующий шаг.

## Подтверждённая база и открытые задачи — 13 октября 2026

Диагностика менеджера теперь проверяет совпадение `brands`, `mobile` и `platform`
между обычным `userAgentData` и `getHighEntropyValues` в document/dedicated worker;
отсутствующее поле и `0` вместо `false` считаются ошибкой. 11 новых негативных
контролей входят в 336 Python-проверок Native runtime. Реальный owned-прогон
на неизменённом браузере 001–027 прошёл для desktop en-US/de-DE и Mobile Web
390×844/DPR 3: `D:\CamouFlowNative\manager-owned-hints-screen-001-027-v1.json`.
Исходная вкладка и её сеть сохранены; core/входные файлы проверены до и после.
Это аудит согласованности, не новая подмена и не admission патчей 028–036.
Также проверяются тип/положительность CPU и конечный диапазон WebIDL float
для RAM; совпадающие некорректные значения в document/worker не считаются
здоровым профилем. Явное отсутствие device-memory API (`null`) допустимо,
пропущенное поле — нет; реальные 128 CPU не ограничиваются искусственно 64.
365 Native runtime Python-проверок прошли. Owned desktop/mobile прогон:
`D:\CamouFlowNative\manager-owned-hardware-hints-001-027-v1.json` — три случая,
core/входные файлы неизменны, только старый feature-off браузер 001–027.

Полная сборка 001–036 была остановлена по просьбе пользователя на 58/4994 задачах;
после его команды возобновлена на j1, без удаления объектов и кэша.
Лог этого возобновления: `D:\CamouFlowNative\surface-batch-001-036-chrome-j1-v6.log`.
Затем по команде пользователя сборка переключена на j4 с сохранением кэша.
Попытка v7 завершилась после 100 задач из 4843: две ошибки C++ в WebGL,
а не OOM — `base::expected` нельзя проверять через `!`, и `base::BindOnce`
не принимает захватывающую лямбду. Патч 0037 использует `has_value()` и
stateless callback с `WrapPersistent(this)`, сохраняя восстановление pack-state.
Реальная компиляция ранее падавшего translation unit прошла с исходными flags:
`D:\CamouFlowNative\webgl-readback-compilation-001-037-v2\proof.json`.
Проверки неизменности source/core/GN прошли; это не новый проверенный браузер.
Полная сборка 001–037 вновь запущена на **j4** без удаления объектов.
Лог этой попытки: `D:\CamouFlowNative\surface-batch-001-037-chrome-j4-v8.log`.
Она завершилась после 449 задач: renderer сравнивал `mojo::StructPtr` с `nullptr`.
Патч 0038 сохраняет проверку наличия legacy Canvas carrier через `!is_null()`.
Ранее падавший `render_frame_impl.cc` скомпилирован с исходными target flags
в отдельном output; source/core/GN неизменны:
`D:\CamouFlowNative\renderer-pointer-compilation-001-038-v1\proof.json`.
Replay цепочки 001–038 прошёл по 125 путям. Следующая полная попытка — j4,
с сохранением уже собранных объектов; runtime 001–038 ещё не подтверждён.
Лог завершённой сборки: `D:\CamouFlowNative\surface-batch-001-038-chrome-j4-v9.log`.
Сборка 001–038 успешно завершилась на j4 за 31 минуту 11 секунд.
Реальные worker startup проверки прошли **40/40**. Комбинированная проверка
Canvas/OfflineAudio подтвердила шесть фаз baseline/профилей/перезапусков и изоляцию,
но общий результат **FAIL**: отсутствие политики вызвало краш при запрещённом
переходе из `READY_TO_COMMIT`. Патч 0039 отменяет запрос через владеющий им
RenderFrameHost, сохраняет `ERR_ABORTED` и очищает speculative host без ослабления
политики. Требуются пересборка и повторный runtime-прогон.
Доказательства на D: `worker-surfaces-startup-001-038-v1.json`,
`combined-surfaces-001-038-v1.json`. Это не результаты CAPTCHA/антибот-сайтов.
Replay 001–039 прошёл по 125 путям; Python-проверки: **1949 passed**, Ruff F — clean.
Следующая инкрементальная сборка остаётся на j4, без удаления кэша:
`D:\CamouFlowNative\surface-batch-001-039-chrome-j4-v10.log`.
Сборка 001–039 завершилась на j4 за **8m15.04s**. Повторный комбинированный
runtime-прогон v2 прошёл **7/7**: контрольная страница выполняет скрипт; при
отсутствии политики связанный Document request получает `ERR_ABORTED`, frame,
loader и history неизменны, commit/скрипт отсутствуют, браузер отвечает.
Начальный persistent-driver timeout сохранён отдельно и не считается PASS.
Доказательство: `D:\CamouFlowNative\combined-surfaces-001-039-v2.json`.
Патч **0040** включает guard для уничтожения WebContents в finish observer и
восемь поздних cancellation/regression случаев. Source replay прошёл по 125 путям;
syntax/type-check обоих C++ файлов прошёл ранее. Нативный surface-navigation gate
теперь требует **42** точных случая. Запускается сборка `content_unittests` на j4,
без параллельного Chrome builder; затем выполнение тестов и новая проверка браузера.
Лог: `D:\CamouFlowNative\surface-navigation-001-040-v1-build.log`.
До этих проверок 0040 не считается runtime-готовым или релизным.
Эта попытка завершилась после 276 задач: fixture child transport обращался к
приватному RFH override. Это C++ access error, не OOM. Патч **0041** вызывает
тот же реальный обработчик через публичный `mojom::FrameHost`, без расширения API.
Ранее падавший fixture скомпилирован в отдельный объект с target flags;
source/core/GN unchanged: `child-interface-compilation-001-041-v1/proof.json` на D.
Replay 001–041 прошёл по 125 путям. Повторный surface-navigation gate остаётся
на j4 и использует сохранённый кэш; 42 случая ещё не выполнены.
Новый лог: `D:\CamouFlowNative\surface-navigation-001-041-v2-build.log`.
Этот test binary успешно собрался за **31m17.34s**, но завершился до выполнения
тестов: глобальный `GURL`/origin в initial-policy fixture использовал URL registry
раньше регистрации content schemes. Патч **0042** заменяет глобальную инициализацию
на вызываемую тестом фабрику, без отключения DCHECK или изменения production API.
Исправленный fixture отдельно скомпилирован; proof на D:
`initial-origin-fixture-compilation-001-042-v1/proof.json`.
Следующий j4 прогон сохраняет объекты; 42 теста ещё не считаются выполненными.
Лог: `D:\CamouFlowNative\surface-navigation-001-042-v3-build.log`.
После 0042 test binary пересобрался за **49.26s** и запустил проверки. Они выявили
пропуск production wiring: throttle registry проверял только Canvas switch,
поэтому surface missing-policy не проходил readiness-throttle; about:blank
отмена ломала предположения NavigationSimulator. Патч **0043** подключает
существующий throttle для всех явных non-off document modes в обоих путях.
Изменённый production файл отдельно скомпилирован; proof на D:
`surface-throttle-compilation-001-043-v1/proof.json`. Replay прошёл по 126 путям.
42-case gate повторяется на j4 с сохранением кэша. Прошлый partial/crashed run —
не PASS. Лог: `D:\CamouFlowNative\surface-navigation-001-043-v4-build.log`.
После 0043 test binary пересобрался за **56.10s**; missing-policy checks прошли
дальше. Следующий сбой был в NavigationSimulator: конфликт режимов немедленно
отменяет about:blank, не оставляя pending entry. Fixture-only патч **0044**
проверяет этот путь через реальный NavigationController, сохраняя `ERR_ABORTED`,
запрет commit и прежний URL. Production cancellation и network-path simulation
не изменены. Исправленный fixture скомпилирован; replay прошёл по 126 путям.
Proof: `inline-rejection-compilation-001-044-v1/proof.json` на D.
Полный 42-case gate повторяется на j4; лог:
`D:\CamouFlowNative\surface-navigation-001-044-v5-build.log`.
Следующий run дошёл до observer closure: Chromium запрещает удалять WebContents
во время уведомления списка observers. Fixture-only патч **0045** запрашивает
отложенное закрытие через weak-bound task; teardown инвалидирует ожидающий task.
Общий driver inline-cancellation используется для конфликта и четырёх late-loss
случаев. Проверки `ERR_ABORTED`, отсутствия commit, recovery и удаления вкладки
сохранены; ни один из 42 случаев не пропущен. Fixture отдельно скомпилирован;
replay прошёл по 126 путям. Proof: `observer-fixture-compilation-001-045-v1/proof.json`.
Повторный j4 gate: `D:\CamouFlowNative\surface-navigation-001-045-v6-build.log`.
В следующем GPU-пакете подготовлен четырнадцатый passthrough fixture:
multisample metadata сравнивается с фактическим `GL_RENDERBUFFER_SAMPLES`,
а не с запрошенным числом samples. Формат RGBA8 сам по себе не означает
single-sample readback: consumer отдельно отклоняет `samples != 0`.
C++ fixture пока не скомпилирован и не выполнен.
Объединённый replay identity/readback и изолированная генерация Mojo/GPU
успешны на исходниках 001–036; active sources не изменены. Приватное доказательство:
`D:\CamouFlowNative\identity-readback-classification-001-036-batch-v1.json`.
`compiled=false`, `mode_enabled=false`, `privacy_admitted=false`.
Отдельно реально скомпилированы и выполнены **14 standalone C++ codec tests**
через checkout `clang-cl` и VS STL: `scripts/verify_native_gpu_codec.py`.
`D:\CamouFlowNative\gpu-metadata-codec-classification-native-v1.json` подтверждает неизменность
входов и активных core/GN. Это не компиляция команды/decoder/Blink в Chromium,
не проверка ABI полного браузера и не admission защиты.
Encoder и decoder теперь отклоняют противоречивое сочетание byte-colour claim
с float/integer/packed/unknown format; ложный флаг и реальный multisample count
сохраняются без повышения совместимости. Изменён только будущий GPU-пакет,
не исходники активной сборки 001–036.

Подготовлен отдельный unit gate `--target worker-surfaces` в
`scripts/verify_native_privacy_units.py`: строго 55 завершённых случаев —
25 существующих Canvas worker endpoint/consumer cases и 30 Surface cases из
0031. Он требует зарегистрированную цепочку, включая исправление 0036;
missing/duplicate/skipped/foreign/failed результаты не принимаются.
Исторический `delivery` gate не расширен молча и сохраняет свой контракт.
Новый gate ещё не запускался: он компилирует `content_unittests`, поэтому
использовать его только после разрешённого возобновления сборок. Это не
проверка first-script ordering реальных worker hosts и не admission браузера.

Установка managed runtime проверяет свободное место на томе хранилища перед
копированием архива и повторно после проверки всех tar entries, до распаковки.
При нехватке места staging удаляется, текущий и предыдущий релизы не меняются.
Проверка не резервирует пространство: параллельная запись другим процессом
всё ещё может привести к обычной ошибке файловой системы во время установки.

Glint — настоящий pinned fork Chromium/Blink с C++/Mojo-патчами, а не только
инъекции поверх Chrome. При этом менеджер использует Playwright/CDP для управления
и SDK-настроек: это не отсутствие CDP и не нативная подмена всех Web API.
Один профиль запускается в одном persistent BrowserContext; вкладки разделяют
его хранилище. Document/iframe/worker имеют собственные execution contexts,
но это не отдельный BrowserContext на каждую вкладку.

| Область | Подтверждённая граница на момент составления плана |
| --- | --- |
| Windows, патчи 001–027 | Связанный браузер: 160 проверок восьми runtime-gates; receipt и core DLL проверены. Внешние результаты старых версий не переносить |
| CPU/RAM, шрифты, WebRTC, webdriver/headless, ограниченный CDP-сигнал | Нативные политики есть; включение в менеджере требует admission конкретного runtime |
| Ключи/StorageKey/BrowserContext | 43 native readiness/key cases и 20 реальных context cases прошли; это не доказательство всех renderer/worker-путей |
| IPC и consumers | 34 endpoint/consumer cases прошли; совместный прогон context/delivery — 54 cases, не дополнительные независимые 54 проверки |
| Worker startup | 40 runtime-проверок прошли в developer-режиме; все четыре Blink handoff cases прошли после test-only исправления 0028. Browser core/receipt/GN не изменились; Canvas/admission этим не подтверждаются |
| Исходники 001–036 | Зарегистрированы; полноценный новый браузер не подтверждён. После LLVM OOM на j4/j2 сборка j1 дошла до ошибки неполного Mojo-типа в worker service. Исправление 0036 прошло dedicated-worker object gate; полная сборка продолжена на j1 без очистки кэша |
| Document delivery до JS | Producer/transport и document/worker surface policy зарегистрированы в новой цепочке; first-script delivery и безопасное восстановление при final mismatch ещё требуют проверки нового бинарника |
| Canvas / Offline Audio | Нативные кандидаты зарегистрированы; upstream baseline не доказывает защиту. Capability в менеджере не активирована |
| WebGL/WebGPU | Частичный WebGL readback зарегистрирован; будущие исправления clipping/halo и GPU metadata transport остаются отдельным пакетом. WebGPU readback не завершён |
| Устойчивая идентичность | Подготовлены шесть патчей derivation/mode/transport/handoff/launch, Python reference и проверки наблюдений; нативный runtime этого режима ещё не проверен |
| Совместный следующий пакет | 12 identity/readback патчей прошли изолированный source replay и Mojo/GPU codegen; добавлены texture attachment/binding fixtures. Это не компиляция и не выполненные C++-тесты |
| UA/Client Hints, Screen/Intl, storage | Часть конфигурации и диагностик есть; нужна единая карта покрытия, а не вывод «отсутствует» из краткого отчёта |
| Сеть и внешние сервисы | Штатный Chromium stack; полный сравнительный TLS/HTTP/DNS-прогон и Core-сайты для 001–027 не подтверждены |
| Название и логотип Chromium | Branding-патч подготовлен; проверить фактический бинарник после применения |

Доказательства и ограничения: [верификация](NATIVE_VERIFICATION.md),
[матрица результатов](GLINT_TEST_MATRIX.md),
[черновики доставки](../native/drafts/document_delivery/README.md).
Количество шагов сборки — не количество тестов и не процент готовности.
Оценки «75% базы / 30% антидетекта» не использовать как инженерную метрику.

## Приоритеты и обязательные gates

### Связанные пакеты вместо пересборки после каждого исправления

Контрольная точка 14 октября: на неизменённом браузере 001–047 прошли семь фаз
combined surfaces и 24 nested Canvas cases; строгий HTTP/JS Client Hints gate
прошёл 18 проверок (восемь document/frame, шесть worker JS, четыре отказа
некорректного UA). Cross-origin fixture получил явную delegation только для
своего localhost origin; это исправление тестового opt-in, не подмена API.
На source 001–048 выполнены 31 нативный readback case и C++ preflight всей
Identity/GPU-композиции (22 + 6 единиц). Новые 41 identity fixtures, линковка
пакета и его browser runtime всё ещё впереди; прежние сбои сохранены.
Уточнение состава: 41 новая тестовая функция означает **50 GTest cases**, а не
41 execution. Три DocumentLoader-теста разворачиваются в четыре режима каждый.
Replay gate проверяет suite/name/macro и единственность определений, а также
все четыре pinned storage/link режима; source-проверка не считается запуском.

Следующий пакет: стабильная profile identity, доставка в documents/iframe/workers
и GPU metadata/readback. Готовить его в изолированной копии, не меняя активную
сборку. Source/codegen/C++ preflight выполнять для всей композиции, затем одну
сборку пакета и полный набор нативных/runtime-проверок. Обычные ошибки собирать
за один прогон, исправлять связанной группой; OOM/crash/нарушение изоляции могут
блокировать дальнейшее исполнение и не считаются проверенными случаями.

Пакет перенесён целиком в исходники как 0049–0058: точное совпадение с reviewed
composition и ordered replay всех 58 патчей подтверждены. Сохранены source-before
копии для отката; браузер 001–047, GN и receipt не изменились. Proof на D:
`identity-gpu-source-integration-0049-0058-v1/proof.json`. Новые native targets:
identity-keys 62, identity-contexts 37, identity-transport 20, identity-handoff 15
(134 cases, включая 50 новых и 84 legacy). Регистрация не означает успешной
линковки, исполнения этих тестов или готовности режима; admission закрыт.

Команда пакетного C++ preflight:

```powershell
.venv\Scripts\python.exe scripts/verify_native_identity_readback_batch.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\identity-readback-package-new.json --collect-cpp-errors
```

Она собирает обычные ошибки по 22 identity и шести GPU единицам, но останавливает
компиляцию при crash/timeout/OOM и перечисляет `not_checked`. Полная композиция
прошла этот C++ режим на 001-048: 22 + 6 единиц, без пропусков; proof на D:
`identity-readback-combined-cpp-001-048-v3.json`. Это проверка типов, не линковка,
исполнение 41 identity fixture или включение режима. Тяжёлые preflight и
сборки запускать последовательно, сохраняя запрошенный `j4` и готовый кэш.
Отдельный успешный модуль не заменяет проверку связанного пакета.

| Приоритет | Работа | Условие завершения |
| --- | --- | --- |
| P0 — выполнено | Blink handoff target | Четыре точных cases прошли без skipped; хеш тестового бинарника и неизменность browser core/receipt/GN подтверждены. Отчёт: worker-handoff-001-028-fixture-lifetime-j4.json |
| P0 | Доставка до первого JS/API | Проверены browser-owned partition commitment, финальное состояние документа, владение seed, startup/shutdown всех применимых контекстов |
| P1 | Матрица Web API и конфигурации | Для каждого API указаны support, owner, механизм применения, проверенная сборка, контексты и пробелы |
| P1 | Сетевая диагностика | Сопоставимые stock Chromium/Glint, DNS/прокси/TLS/HTTP/заголовки; ограничения маршрута и протокола явно записаны |
| P1 | Canvas → GPU → Audio | Последовательный opt-in с API semantics, изоляцией, совместимостью и комбинированными gates |
| P1 | Compatibility Test Suite | Обычные сайты/fixtures, мультимедиа, безопасность, хранилища, crash/restart и измеренные ресурсы |
| P2 | Релиз и сопровождение | Воспроизводимый пакет, происхождение, обновление/rollback, восстановление и Chromium security rebase |

P0 блокирует активацию новых privacy capabilities. Независимые P1-диагностики,
спецификации и изолированные черновики можно готовить во время сборки,
не меняя её входные файлы. Не копить все модули без промежуточных gates:
после базы объединять только совместимые проверенные изменения.

## Уточнения после изучения Fortress и Fury

[Статья Fortress](https://habr.com/ru/articles/1057754/) подчёркивает нативный
уровень и согласованность контекстов. Это полезный ориентир, но нативный getter
сам по себе не исключает обнаружение автоматизации. Заявления автора о PASS
не переносим в результаты Glint; утверждение о неизбежном обнаружении любой
JS-техники не принимаем как доказанную универсальную теорему.

[Статья Fury](https://habr.com/ru/articles/1081984/) предлагает сначала измерять,
затем менять движок; различать изменённые значения и нарушенное поведение API.
Описанный аудит одного чужого профиля не доказывает состояние всего продукта.
Новый план ниже — наша адаптация метода, не обещание повторить их результаты.

| Слой | Отдельная задача Glint | Граница доказательства |
| --- | --- | --- |
| Браузерные поверхности | Нативные политики, согласованность контекстов и API | Не доказывает качество IP или поведения пользователя |
| Управление/CDP | Проверить следы подключения, команд и обработки консоли | Патч Error getters не закрывает весь CDP |
| Сеть | Проверить реальные браузерные TLS/HTTP запросы и маршрут | Chromium/BoringSSL по происхождению не заменяет измерение |
| Сессия | Контролируемые действия, permissions и совместимость | Хороший fingerprint не гарантирует прохождение серверного антифрода |

## Этап 0. Измеритель до новых поверхностных патчей

Расширить существующие диагностические инструменты, не создавать второй
параллельный тестовый стек. Ориентир —
[Fury detect-suite](https://github.com/furyteamtop/fury-antidetect-browser/tree/main/tools/detect-suite).

| Режим измерения | Что сравнивать | Правило |
| --- | --- | --- |
| Повторяемость | Один профиль, origin и конфигурация: чтения и restart | Стабильные поля совпадают; динамические поля классифицируются отдельно |
| Совместимость | Stock Chrome и Glint, сопоставимые version/OS/backend/режим | Поведение API сохраняется, кроме явно выбранных ограничений политики |
| Изоляция | Разные профили, clone/restore, разные partition sites | Меняются только предусмотренные контрактом значения; совпадение или отличие одного hash не является итоговым verdict |
| Внутренняя согласованность | Документы, iframe и доступные workers | Сравнивать только API, которые должны присутствовать в обоих контекстах |

Схема отчёта должна включать version, configuration, build hashes, context,
surface, presence/support, value digest, error и duration. Отдельно учитывать
Not supported, Not applicable, timeout и collector error. Не требовать наличия
`screen` или `webdriver` в Worker; permissions сравнивать после нормализации
эквивалентных состояний. Не трактовать `document.fonts.check()` как доказательство
установленного шрифта: нужны метрики и fallback-контроль.

Использовать контролируемый HTTP loopback/HTTPS стенд, не `file://` и не
отключение security. Покрыть same-origin, `about:blank`, `srcdoc`, cross-origin
OOPIF, dedicated/shared/service workers и AudioWorklet. Проверять присутствие
и корректный сбор каждого контекста; нельзя терять отсутствующие результаты.
Collector логирует успешные и ошибочные запросы, ограничивает размер/время
приёма и хранит сырые данные только приватно. JS probe наблюдает API, не подменяет их.

**Выход:** отрицательный контроль обнаруживает известную автоматизацию;
обычный Chrome не получает ложные ошибки из-за неверного сравнения контекстов.
Несовпадающие версии Chrome/Glint явно отмечаются как confounder, а не баг патча.

## Этап 1. Зафиксировать новую базу

1. Дождаться фактического окончания сборки. При ошибке сохранить полный лог,
   определить compilation/OOM/linking-причину и чинить её, не стирая кэш.
2. Сверить receipt, patch hashes, Chromium revision, GN args и SHA-256
   executable/core DLL. Исключить смешанный output после прерванной сборки.
3. Запустить `verify_native_suite.py` и `verify_native_privacy_units.py` из
   [инструкции сборки](../native/BUILDING.md) с новыми путями отчётов.
4. Проверить обычную навигацию, формы, загрузки, скриншоты, Recorder/replay,
   persistent storage и закрытие процессов. Настройки профиля не должны
   незаметно заменяться значениями по умолчанию.
5. Сделать внешний прогон по [матрице](GLINT_TEST_MATRIX.md): Core-сервисы,
   прямой маршрут и каждый прокси; ручной headed и автоматизированные режимы
   отдельно, минимум три повторения, stock Chrome как отрицательный контроль.
6. Опубликовать очищенную таблицу именно этой сборки, включая Not run,
   Unavailable и Not verified. Для CAPTCHA сохранять подтверждение backend,
   не токен и не только зелёную галочку.

### Отдельный CDP/network baseline

- Сравнить ручной запуск без клиента, подключение CDP, отдельный
  `Runtime.enable` и штатный Playwright/Recorder. Записать фактические команды,
  launch flags и доступность диагностических hooks; сценарий без CDP измерять
  страницей/collector, а не скрытым подключением Playwright.
- Проверить консоль, descriptors, error getters, stack traces и повторяемые
  timing-пробы. Прогрев, размер объектов, загрузку CPU и разброс фиксировать;
  не переносить коэффициент времени из статьи на наш компьютер.
- Любое изменение CDP-клиента проверять на событиях, execution contexts,
  навигации, iframe, Recorder и teardown. Не отключать `Runtime.enable`
  вслепую и не считать исправленный консольный сигнал полной невидимостью.
- Снять TLS/HTTP2/HTTP3 observations браузером при доступности протоколов,
  сопоставить с Chrome на том же маршруте. Порядок TLS extensions/GREASE может
  давать изменчивые значения; не требовать постоянного JA3. Патч BoringSSL
  планировать только после воспроизводимого необъяснённого расхождения.
- Отдельно учесть proxy relay, DNS, WebRTC, redirects и запросы загрузки
  ресурсов/обновлений. Browser proxy не доказывает, что manager-трафик идёт туда же.

**Выход:** воспроизводимая база с точными хешами и списком ограничений.
Отдельный результат сайта не является разрешением всех privacy capabilities.

## Этап 2. Жизненный цикл ключей и безопасная доставка

| Работа | Критерий приёмки |
| --- | --- |
| Сохранить пройденные context/endpoint gates; исполнить четыре Blink handoff cases | Exact source replay; все требуемые именованные тесты завершены, без skipped; тестовый target не выдаётся за новую browser-сборку |
| Проверить настоящий Chrome ProfileImpl и incognito | Реальный startup/shutdown, отдельная OTR-идентичность, без чтения ключа постоянного профиля |
| Определить версионированный контракт идентичности | Повторный запуск сохраняет идентичность; clone/restore/export следуют явной политике; повреждённый ключ не регенерируется скрыто |
| Спроектировать browser → renderer IPC | Корневой ключ никогда не передаётся; только ограниченные производные данные, привязанные к нужной поверхности/контексту |
| Использовать доверенный partition state | Renderer не выбирает чужой StorageKey, top-level site или профиль; opaque/third-party контексты имеют явную семантику |
| Проверить навигацию и жизненный цикл | Redirect, cross-origin iframe, BFCache, prerender, reload, process reuse/crash не дают старому контексту чужую идентичность |
| Определить workers | Dedicated/shared/service workers, OffscreenCanvas; для непокрытого случая capability блокируется, не применяется глобальный ключ |
| Ограничить ожидание готовности | Deadline/cancellation, shutdown во время loading, reentrancy, очереди и отсутствие UAF; отказ без незаметного fallback |
| Защитить транспорт конфигурации | Ключи/чувствительные значения не появляются в argv, environment дочерних процессов, логах и crash diagnostics; при необходимости использовать ограниченно наследуемый Windows HANDLE/IPC с проверкой получателя |

**Выход:** тестируемый контракт доставки до подключения новых поверхностей.
Стабильная идентичность профиля и межсайтовая unlinkability — разные свойства;
выбранная partition-политика должна быть документирована и проверена отдельно.

### P0: конкретный следующий пакет доставки

1. Выполнено: четыре Blink cases прошли; результат и хеши сохранены в worker-handoff-001-028-fixture-lifetime-j4.json. Последний проверенный браузер остаётся 001–027, patch 0028 меняет только тест.
2. Довести document carrier и bounded readiness barrier, зарегистрировать и
   исполнить их fixtures только после проверки producer/consumer-контракта.
   Подготовленный commit transport уже передаёт owned payload в DocumentLoader,
   проверяет окончательный partition и сохраняет clone state; три translation
   units прошли syntax, не runtime. Browser producer/регистрация throttle тоже
   подготовлены; при недоступной browser policy запрос отменяется до commit.
   Следующие узлы — исполнение fixtures, end-to-end first-script delivery и
   нормальный отказ при несовпадении финального partition вместо renderer CHECK.
   Renderer-first-script fixtures подготовлены: оба pre-script callback, inline
   Canvas smoke и контроль без политики. Они прошли syntax с GC plugin, но не
   исполнение и не проверку полного browser → renderer пути.
   Отдельные NavigationSimulator fixtures подготовлены для HTTP/about:blank:
   flag-off, missing-policy abort с сохранением предыдущего URL и ready payload.
   Шесть предполагаемых cases ещё не исполнены. Финальный mismatch нельзя
   исправить простым return: после teardown нужна согласованная обработка frame
   либо решение до teardown; CHECK пока сохраняется, capability заблокирована.
3. Связать browser-owned partition commitment с финальным StorageKey до
   установки документа. В pinned Chromium navigation key может быть provisional:
   готовность ключевого сервиса не доказывает окончательность partition.
4. Проверить initial empty, about:blank/srcdoc, nested iframe/OOPIF, redirects,
   renderer-only replacement, synthetic DOM documents, BFCache/prerender.
   Canvas читает политику действующего execution context, не URL DOM-owner.
5. Проверить dedicated/shared/service worker classic/module, вложенные workers,
   раннее уничтожение, host disconnect, late reply и bounded очереди. Для
   shared-control черновика нужны границы 64/65, порядок и освобождение портов.
6. Проверить несколько профилей одновременно, crash/restart и стабильность
   производных seed внутри заданной partition/surface. Root/seed не публиковать
   в JS, логах, crash dumps или экспортах; тестовые маркеры не использовать как
   production-идентичность.

Worker probe корректирует Playwright-флаг ThirdPartyStoragePartitioning только
для диагностики. Обычный manager launch пока не наследует эту корректировку:
сначала проверить фактические launch flags и согласовать partition-политику,
затем допускать capability. Не переносить результат probe на штатный запуск.

## P1. Единая матрица API, конфигурации и сети

Расширять существующие configuration/identity/diagnostics и verifier-скрипты.
Не вводить второй Policy Manager: сначала зафиксировать единственного владельца
каждого параметра, версию схемы, validation и путь применения. Политика должна
достигать применимых document/worker/network/graphics компонентов до первого
использования API; отсутствие поддержки — явный отказ, не скрытый fallback.

| Поверхность | Обязательное покрытие |
| --- | --- |
| Navigator / identity | UA, платформа, CPU/RAM, язык, API presence; SDK/CDP и C++ механизмы различаются в отчёте |
| Client Hints | JS low/high entropy и HTTP Sec-CH-UA*, Accept-CH/Permissions-Policy, secure context, redirect и поддерживаемые workers |
| Screen / DPR / viewport | Screen/available area, zoom, размеры окна/viewport и media queries; не требовать screen в workers |
| Timezone / Intl | Locale, Accept-Language, Date/Intl, restart и все применимые контексты |
| Canvas / GPU / Audio | Support и API semantics отдельно от privacy capability; readback/export/limits и применимые worker-пути |
| WebRTC | Permissions, ICE/IP, proxy routing и отсутствие непредусмотренного direct egress |
| Storage | Cookies, localStorage, IndexedDB, Cache Storage, service-worker registrations; разные профили, partition и crash/restart |

Для каждой строки записывать owner, режим/конфигурацию, support/context,
конкретный gate/report/build и статус: Verified / Partial / Prototype / Missing /
Not run / Not applicable. Сначала инвентаризировать существующие проверки.

| Сетевой слой | Диагностика и критерий |
| --- | --- |
| TLS / JA3 / JA4 | Запросы самого браузера против stock Chromium сопоставимой версии/ОС на том же маршруте; учитывать GREASE/порядок extensions |
| HTTP/2 / HTTP/3 | Реальная negotiation, доступность QUIC через маршрут, настройки и поведение запросов; недоступность H3 не превращать в PASS |
| HTTP headers | UA/Client Hints/Accept-Language согласованы с JS и конфигурацией, включая redirect/subresources |
| DNS / proxy | Контролируемые наблюдения резолвинга и маршрута, authenticated proxy failure, WebRTC и отсутствие direct fallback |
| Manager / updates | Отдельно измерять трафик менеджера, загрузчика и обновлений: browser proxy не покрывает их автоматически |

Не писать собственный TLS stack и не патчить BoringSSL без воспроизводимой
причины. Совпадение JA3/JA4 не доказывает невидимость автоматизации.

## Этап 3. Canvas — первый новый модуль

- До патча выбрать и описать алгоритм, область действия и режим opt-in.
  Не менять случайно результат каждого чтения и не модифицировать отображение
  страницы ради изменения экспортируемого fingerprint.
- Покрыть нативные пути `getImageData`, `toDataURL`, `toBlob`,
  `OffscreenCanvas.convertToBlob`, документы/iframe/workers.
- Проверить согласованность чтений/экспорта, разные профили и partition sites,
  перезапуск, клонирование, resize/reset, пустой canvas, alpha/цветовые форматы,
  недопустимые размеры и существующие security exceptions tainted canvas.
- Сравнить обычные рисунки, редактор изображений, графики, сохранение PNG/JPEG
  и производительность с отключённой политикой и stock Chrome.
- Проверить обнаружимые расхождения между API; количественно оценить визуальные
  изменения и накладные расходы. Не ограничиваться зелёным CreepJS.
- Добавить crop/абсолютные координаты, чтение по частям, повторный экспорт,
  read → write → read и перенос в текстуру. Определить поведение повторной
  обработки: нельзя незаметно накапливать возмущение. Для PNG сравнивать
  декодированные пиксели; для JPEG учитывать потери кодека, а не требовать
  невозможного побайтового равенства. Несколько известных рисунков должны
  проверять применимость политики, а не только отличие от stock hash.

**Выход:** отдельная capability Canvas, включаемая только для проверенного
бинарника и проверенной комбинации настроек.

## Этап 4. GPU, затем Audio

| Модуль | План | Что нельзя считать успехом |
| --- | --- | --- |
| WebGL | Исследовать снижение раскрытия renderer/vendor, согласованность extensions/limits и защиту readback; проверить WebGL 1/2 и обычный рендеринг | Выдуманная GPU-модель при несовпадающих возможностях |
| WebGPU | Отдельно проверить adapter info, features/limits, compute/render/readback и worker-пути | Перенос WebGL-результатов без WebGPU-проверки |
| Audio | После Canvas: детерминированная политика OfflineAudioContext, чтения буферов и анализаторов; различать offline/readback и воспроизведение | Случайная смена sample rate или ухудшение звучания |

Для каждого модуля нужны отдельная спецификация, нативный патч, негативные
контроли, cross-context/restart проверки и измерение совместимости. Перед
реализацией сверять исследования с актуальными первичными источниками.

Новые capabilities разрешается сужать только согласованно: заявленные
extensions/features/limits должны соответствовать фактическому созданию
контекстов и исполнению операций. Запрещённую возможность проверять на запросе,
не только убирать строку из перечисления. Новые upstream-поля включать в аудит.
Для перечня исследуемых поверхностей использовать актуальную
[техническую карту Fury](https://github.com/furyteamtop/fury-antidetect-browser/blob/main/docs/02-fingerprint-surface.md),
сверяя её с нашим pinned Chromium и реальным аппаратным backend.

## Этап 5. Согласованность и интеграция в менеджер

- Проверить UA, UA Client Hints (включая HTTP и high-entropy), реальную версию,
  язык/Accept-Language/Intl/timezone, document/iframe/workers.
- Не выдавать Web Emulation за Android/iOS. Настройки должны быть связными,
  не независимым набором противоречащих друг другу ручек.
- Прогнать все политики одновременно: несколько профилей, вкладок и контекстов,
  последовательные/параллельные запуски, перезапуск и смена прокси.
- Проверить cookie/localStorage/IndexedDB/Cache Storage/service-worker isolation;
  key partitioning не заменяет изоляцию самого браузерного хранилища.
- В UI показать supported/verified/blocked и конкретную причину отказа.
  Сохранённый privacy draft не должен выглядеть как активная защита.
- Проверить применение настроек, устаревание compatibility report при их
  изменении, reset, ошибки запуска, keyboard accessibility и rollback.
- Расширить аудит: screen/available area/DPR/zoom, font metrics и fallback,
  geometry (`getClientRects`), media-device identifiers/permissions,
  speech voices, codecs и EME. Это сначала измерение, не автоматическое
  обещание подменить каждую поверхность. Отсутствие DRM/codec честно отражать;
  не включать сторонний proprietary CDM в пакет без права распространения.

**Выход:** безопасный opt-in через существующую систему capabilities, без
непроверенных fallback и без лишнего дублирования менеджера.

## Этап 6. Выпуск и поддержка

### P1: Compatibility Test Suite перед выпуском

Поверх существующего suite добавить формализованный набор owned fixtures и
публичных страниц без аккаунтов: формы/навигация/загрузки, Recorder/replay,
Canvas/графики/WebGL, мультимедиа и permissions. Проверять CSP/origin/tainted
security semantics, изоляцию данных и владельцев процессов, concurrent profiles,
shutdown/crash/restart и upgrade старого профиля без потери данных.
На одинаковой машине и конфигурации измерять startup/teardown, RAM/CPU на профиль,
latency readback и crash rate с размером выборки. Порог регрессии определить по
измеренному baseline до admission, не придумывать проценты после запуска.

### P2: release gates

1. Branding Glint зарегистрирован как 0060 и применён к исходникам; сборка 001–060
   запущена на j4 после проверки отдельной копии 001–059 для отката. Проверить ресурсы, имя продукта,
   окно, иконки и credits. Не переименовывать криптографические домены/engine ID
   ради косметики без миграционного анализа.
2. Проверить актуальность Chromium и security rebase до production admission.
   Новый upstream требует повторного replay, сборки и полного набора проверок.
3. Довести чистую Windows-сборку: снять CIPD transport blocker из
   [аудита](GLINT_WINDOWS_BUILD_AUDIT.md), проверить sync/hooks/patching/build.
4. Подготовить официальный staging, проверить полный relocated payload,
   установку/активацию/health check/rollback и отсутствие утечек процессов.
5. Проверить desktop release gate. Публикация CamouFlow manager и выпуск Glint
   engine — разные операции; сайт должен отражать их действительную готовность.
6. Подписанные обновления/каталог проектировать отдельно, с проверкой
   происхождения и безопасным отказом. Без этого development bundle остаётся
   явно обозначенным неподписанным артефактом.
7. Crash reporting — только opt-in и после редактирования чувствительных данных;
   профили, URL с токенами, seed/root keys и содержимое страниц не отправлять.
   Восстановление данных и rollback проверять на копиях, не на профиле пользователя.
8. Фиксировать versioned manifest, зависимости/toolchain и checksums полного
   пакета. Различать воспроизводимость процесса сборки и доказанную побитовую
   воспроизводимость. Подпись/ключи издателя — отдельный release gate.

Linux/macOS и настоящее мобильное исполнение не входят в текущий Windows-этап.
Linux/macOS отложены пользователем, а не выполнены; полный исходный
кроссплатформенный goal остаётся незавершённым.

## Формат отчёта этапа

| Build / commit | Модуль и конфигурация | Проверки и контроль | Результат | Ограничения / следующий шаг |
| --- | --- | --- | --- | --- |
| Заполнить после фактического выполнения | Точный режим, patch range и хеши | Именованные тесты, маршруты, повторы | Измеренный результат, не обещание | Непроверенные случаи и путь к приватным доказательствам |

Готовность показывать по подсистемам и требованиям: completed/required gates,
число и причины skipped/failed, пробелы покрытия, регрессии после upstream update,
стабильность конфигурации, изоляция, совместимость, crashes и ресурсы. Процент
прошедших тестов допустим только с явным знаменателем и не равен готовности продукта.
Внешние детекторы/CAPTCHA — наблюдения по конкретной сборке/маршруту, не admission.

Четыре Blink handoff cases прошли. Приоритет ближайшей работы: **document producer и
startup/lifetime delivery → матрица API/сети → Canvas → GPU → Audio →
комбинированная совместимость → release admission**.
Критические ошибки безопасности или жизненного цикла блокируют продвижение,
даже если внешний диагностический сайт показывает хороший результат.

## Как использовать внешние реализации

Статьи отражают версии и условия их авторов. Перед переносом идеи проверить
актуальный source, тесты и ограничения; код не копировать без проверки лицензии.
Не вводить Rust/Tauri или чужой агент только ради повторения архитектуры Fury.
Для сравнительного эксперимента фиксировать версии всех движков и одинаковую
матрицу маршрутов/режимов. Не выполнять чужие скрипты на личных профилях и
не публиковать hardware dumps. Этот план добавляет проверки, но не утверждает,
что перечисленные модули уже реализованы.
