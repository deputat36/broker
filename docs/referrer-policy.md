# Браузерная политика referrer

## Задача

Сайт использует рекламную атрибуцию и внешние каналы связи. Даже при отключённом JavaScript браузер не должен передавать внешнему сайту полный путь страницы, query-параметры или fragment.

## Каноническое правило

Общий layout содержит:

```html
<meta name="referrer" content="strict-origin-when-cross-origin">
```

Это означает:

- при переходе внутри `sterlikova-ipoteka.ru` браузер может передать адрес текущей страницы;
- при HTTPS-переходе на другой origin передаётся только origin сайта;
- полный путь, query и fragment внешнему сайту не передаются;
- при переходе с HTTPS на небезопасный HTTP referrer не передаётся;
- правило действует до выполнения JavaScript и при полностью отключённом JavaScript.

## Связь с атрибуцией

Политика браузера дополняет, но не заменяет sanitization в `assets/js/main.js`:

- локальный snapshot хранит страницу без query и fragment;
- внешний referrer сокращается до origin;
- UTM и рекламные click ID сохраняются отдельно по allowlist;
- legacy и повреждённые записи удаляются fail-closed.

## Автоматическая проверка

```bash
python3 scripts/audit-referrer-policy.py ./_site
```

Аудит требует:

- ровно один canonical marker в `_layouts/default.html`;
- ровно один `meta[name="referrer"]` на каждой HTML-странице;
- точное значение `strict-origin-when-cross-origin`;
- размещение элемента внутри `<head>`.

Проверка включена в обязательный post-build suite.
