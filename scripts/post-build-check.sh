#!/usr/bin/env bash

set -euo pipefail

SITE_DIR="${1:-_site}"

required_files=(
  "$SITE_DIR/index.html"
  "$SITE_DIR/robots.txt"
  "$SITE_DIR/sitemap.xml"
  "$SITE_DIR/assets/css/styles.css"
  "$SITE_DIR/assets/css/footer-trust.css"
  "$SITE_DIR/assets/css/online-application.css"
  "$SITE_DIR/assets/js/main.js"
  "$SITE_DIR/assets/js/online-application.js"
  "$SITE_DIR/assets/img/favicon.svg"
  "$SITE_DIR/assets/img/tatyana-hero.webp"
  "$SITE_DIR/assets/img/tatyana-hero-mobile.webp"
  "$SITE_DIR/assets/img/tatyana-avatar.webp"
  "$SITE_DIR/assets/img/tatyana-social.jpg"
)

for file in "${required_files[@]}"; do
  if [[ ! -s "$file" ]]; then
    echo "::error file=$file::Обязательный файл отсутствует или пуст"
    exit 1
  fi
done

if ! grep -q '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' "$SITE_DIR/sitemap.xml"; then
  echo "::error file=$SITE_DIR/sitemap.xml::Sitemap не содержит корректный urlset"
  exit 1
fi

sitemap_count=$(grep -c '<loc>' "$SITE_DIR/sitemap.xml" || true)
if (( sitemap_count < 20 )); then
  echo "::error file=$SITE_DIR/sitemap.xml::В sitemap найдено только $sitemap_count URL"
  exit 1
fi

if grep -q '/404.html' "$SITE_DIR/sitemap.xml"; then
  echo "::error file=$SITE_DIR/sitemap.xml::Страница 404 не должна находиться в sitemap"
  exit 1
fi

if ! grep -q 'Sitemap: https://sterlikova-ipoteka.ru/sitemap.xml' "$SITE_DIR/robots.txt"; then
  echo "::error file=$SITE_DIR/robots.txt::Robots.txt не указывает основной sitemap"
  exit 1
fi

if ! grep -q 'Татьяна Стерликова' "$SITE_DIR/index.html"; then
  echo "::error file=$SITE_DIR/index.html::Главная страница собрана без имени брокера"
  exit 1
fi

if ! grep -q '<link rel="canonical" href="https://sterlikova-ipoteka.ru/">' "$SITE_DIR/index.html"; then
  echo "::error file=$SITE_DIR/index.html::Canonical главной не указывает основной домен"
  exit 1
fi

if grep -q '15 мин' "$SITE_DIR/index.html"; then
  echo "::error file=$SITE_DIR/index.html::На главной осталось неподтвержденное обещание о 15 минутах"
  exit 1
fi

forbidden_pattern='100% одобрение|гарантированное одобрение|точно одобрит|одобрение всем|банк точно одобрит'
if grep -RqiE "$forbidden_pattern" "$SITE_DIR" --include='*.html'; then
  echo "::error::В собранных HTML-файлах найдено запрещенное обещание по ипотеке"
  grep -RniE "$forbidden_pattern" "$SITE_DIR" --include='*.html' || true
  exit 1
fi

legacy_count=$( (grep -RIl 'https://deputat36.github.io/broker' "$SITE_DIR" --include='*.html' || true) | wc -l | tr -d ' ' )
if [[ "$legacy_count" != "0" ]]; then
  echo "::error::В $legacy_count HTML-файлах встречается старый технический домен GitHub Pages"
  grep -Rni 'https://deputat36.github.io/broker' "$SITE_DIR" --include='*.html' || true
  exit 1
fi

python3 scripts/audit-time-sensitive-content.py "$SITE_DIR"
python3 scripts/audit-useful-content-quality.py "$SITE_DIR"
python3 scripts/audit-accessibility-structure.py "$SITE_DIR"
python3 scripts/audit-performance-budget.py "$SITE_DIR"
python3 scripts/audit-conditional-application-assets.py "$SITE_DIR"
python3 scripts/audit-application-runtime-fallback.py "$SITE_DIR"
python3 scripts/audit-thankyou-verification-state.py "$SITE_DIR"
python3 scripts/audit-tatyana-photo.py "$SITE_DIR"
python3 scripts/audit-footer-trust.py "$SITE_DIR"

echo "Post-build проверка успешно завершена: $sitemap_count URL в sitemap"
