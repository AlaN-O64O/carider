# Журнал дефектов (ЛР №7)

Все три ошибки воспроизведены намеренно на коде этой работы: в код вносилась одна правка, запускались тесты, по сообщению об ошибке находилась строка, правка отменялась коммитом `fix:`. Так проверено, что тесты действительно ловят такие ошибки.

| № | Симптом | Тип | Как найдена | Причина и исправление | Коммит |
| --- | --- | --- | --- | --- | --- |
| Д-1 | «Свободных машин нет» появляется не на 15-й секунде, а позже (нарушена граница БП-01) | Логическая | Упали 3 теста, в том числе `test_no_drivers_boundary_at_15_seconds`: `AssertionError: NoDriversError not raised`. В отладчике на строке `if now - started ...` значение `now - started` равно `0:00:15`, как и `SEARCH_TIMEOUT` | В `dispatch/services.py` стояло `>` вместо `>=`: ровно 15 секунд не считались таймаутом. Заменено на `>=` | `fix: граница таймаута поиска включительна (>=)` |
| Д-2 | Экран Э-03 падает с ошибкой 500, когда свободных машин нет | Времени выполнения | Трассировка в тесте `test_search_without_explicit_now_compares_aware_datetimes`: `TypeError: can't subtract offset-naive and offset-aware datetimes` в `find_driver`, строка `if now - started >= SEARCH_TIMEOUT` | `now_utc()` в `orders/services.py` вернула время без часового пояса, а время заказа хранится с UTC; их нельзя вычитать. В `now_utc()` возвращено `datetime.now(UTC)` | `fix: часовой пояс UTC у текущего времени` |
| Д-3 | Страница Э-03 не открывается | Синтаксическая | Тест `test_no_drivers_screen_and_cancel`: `jinja2.exceptions.TemplateSyntaxError: Encountered unknown tag 'endblock' ... currently looking for 'endif'`, шаблон `search.html`, строка 27 | В шаблоне пропущен `{% endif %}` после блока о состоянии поиска. Тег возвращён | `fix: закрыт тег if в шаблоне поиска` |
