# Шаблон SEO-страницы

Этот шаблон нужен для новых страниц услуг, гео-страниц и полезных материалов на сайте ипотечного брокера Татьяны Стерликовой.

## 1. Front matter

```yaml
---
layout: default
title: Название страницы | Татьяна Стерликова
description: Краткое описание страницы до 160–180 символов: кому полезна страница, какая задача разбирается и почему стоит обратиться за консультацией.
permalink: /razdel/slug-stranicy/
breadcrumb: Короткое название
og_type: article
schema: '{"@context":"https://schema.org","@type":"Article","headline":"Название страницы","author":{"@type":"Person","name":"Татьяна Стерликова"},"publisher":{"@type":"Person","name":"Татьяна Стерликова"},"mainEntityOfPage":"https://deputat36.github.io/broker/razdel/slug-stranicy/"}'
---
```

## 2. Hero-блок

```html
<section class="page-hero section">
  <p class="eyebrow">Короткая категория</p>
  <h1>Основной заголовок страницы</h1>
  <p class="lead">Короткое объяснение: какую ситуацию разбирает страница и что человек поймет после чтения.</p>
  <div class="hero-actions">
    <a class="btn btn-primary" href="{{ '/konsultaciya/' | relative_url }}">Разобрать ситуацию</a>
    <a class="btn btn-secondary" href="tel:+79030250807">Позвонить Татьяне</a>
  </div>
</section>
```

## 3. Блок “Главное”

```html
<section class="section">
  <div class="section-head">
    <p class="eyebrow">Главное</p>
    <h2>Что важно понять заранее</h2>
    <p>Короткий абзац, который задает контекст и объясняет, почему тему лучше разобрать до подачи заявки или передачи аванса.</p>
  </div>
  <div class="grid cards-4">
    <article class="card"><h3>Тезис 1</h3><p>Краткое пояснение.</p></article>
    <article class="card"><h3>Тезис 2</h3><p>Краткое пояснение.</p></article>
    <article class="card"><h3>Тезис 3</h3><p>Краткое пояснение.</p></article>
    <article class="card"><h3>Тезис 4</h3><p>Краткое пояснение.</p></article>
  </div>
</section>
```

## 4. Основной контент

```html
<section class="section content-layout">
  <article class="content-main">
    <h2>Первый смысловой раздел</h2>
    <p>Текст простым языком. Не перегружать юридическими и банковскими терминами без объяснения.</p>

    <h2>Что проверить до следующего шага</h2>
    <ul>
      <li>пункт проверки;</li>
      <li>пункт проверки;</li>
      <li>пункт проверки;</li>
      <li>пункт проверки.</li>
    </ul>

    <h2>Чем помогает брокер</h2>
    <p>Объяснить роль специалиста: подготовка, маршрут, документы, расчет, связь с банком и понятный порядок действий.</p>
  </article>

  <aside class="sidebar">
    <div class="seo-panel">
      <h3>Что подготовить</h3>
      <p>Краткий список исходных данных: город, объект, доход, взнос, кредиты, банк, сроки.</p>
      <a class="btn btn-primary" href="{{ '/konsultaciya/' | relative_url }}">Получить консультацию</a>
    </div>
    <div class="seo-panel">
      <h3>Связанные темы</h3>
      <ul>
        <li><a href="{{ '/polezno/' | relative_url }}">Полезные материалы</a></li>
        <li><a href="{{ '/kalkulyator-ipoteki/' | relative_url }}">Калькулятор</a></li>
        <li><a href="{{ '/kontakty/' | relative_url }}">Контакты</a></li>
      </ul>
    </div>
  </aside>
</section>
```

## 5. Чек-лист

```html
<section class="section muted">
  <div class="section-head"><p class="eyebrow">Чек-лист</p><h2>Что проверить</h2></div>
  <div class="checklist">
    <div><strong>1</strong><span>Первый пункт.</span></div>
    <div><strong>2</strong><span>Второй пункт.</span></div>
    <div><strong>3</strong><span>Третий пункт.</span></div>
    <div><strong>4</strong><span>Четвертый пункт.</span></div>
    <div><strong>5</strong><span>Пятый пункт.</span></div>
  </div>
</section>
```

## 6. Связанные материалы

```html
<section class="section related-section">
  <div class="section-head"><p class="eyebrow">Продолжить подготовку</p><h2>Полезные материалы по теме</h2></div>
  <div class="grid cards-4">
    <article class="card"><h3><a href="{{ '/polezno/kak-podgotovitsya-k-ipoteke/' | relative_url }}">Как подготовиться к ипотеке</a></h3><p>Что проверить перед заявкой.</p></article>
    <article class="card"><h3><a href="{{ '/polezno/dokumenty-dlya-ipoteki/' | relative_url }}">Документы для ипотеки</a></h3><p>Что собрать заранее.</p></article>
    <article class="card"><h3><a href="{{ '/kalkulyator-ipoteki/' | relative_url }}">Калькулятор</a></h3><p>Предварительно рассчитать платеж.</p></article>
    <article class="card"><h3><a href="{{ '/konsultaciya/' | relative_url }}">Консультация</a></h3><p>Разобрать ситуацию с брокером.</p></article>
  </div>
</section>
```

## 7. CTA-блок

```html
<section class="section cta-section">
  <div>
    <p class="eyebrow">Нужна помощь?</p>
    <h2>Разберите ситуацию до следующего шага</h2>
    <p>Позвоните или напишите Татьяне: город, объект, доход, взнос, кредиты и что уже известно по банку.</p>
  </div>
  <div class="cta-actions">
    <a class="btn btn-primary" href="tel:+79030250807">8 903 025-08-07</a>
    <button class="btn btn-secondary" type="button" data-copy-phone>MAX</button>
    <a class="btn btn-secondary" href="https://vk.com/tatyanasterlikova" rel="noopener">ВК</a>
  </div>
</section>
```

## 8. Проверка перед коммитом

Перед публикацией новой страницы проверить:

- заполнены `title`, `description`, `permalink`, `breadcrumb`;
- есть минимум 2–3 внутренние ссылки;
- есть ссылка на консультацию или контакты;
- страница добавлена в `sitemap.xml`;
- у страницы нет пустых блоков и битых ссылок;
- текст не обещает результат за банк;
- на мобильном экране заголовок и карточки не ломаются.
