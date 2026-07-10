# Правила UTM-разметки сайта ипотечного брокера

Документ задает единый формат рекламных ссылок для сайта `https://sterlikova-ipoteka.ru/`.

Цель — понимать, откуда человек пришел: из ВКонтакте, рекламного объявления, городской группы, QR-кода, печатной листовки или партнерского размещения.

## 1. Базовый формат

```text
https://sterlikova-ipoteka.ru/страница/?utm_source=источник&utm_medium=формат&utm_campaign=кампания&utm_content=вариант
```

Обязательные параметры:

- `utm_source` — площадка или источник;
- `utm_medium` — тип размещения;
- `utm_campaign` — название рекламной кампании.

Дополнительные параметры:

- `utm_content` — конкретный макет, пост, кнопка или вариант объявления;
- `utm_term` — поисковая фраза или сегмент аудитории, если это действительно нужно.

## 2. Общие правила написания

- Использовать только латиницу, цифры, дефис и нижнее подчеркивание.
- Не использовать пробелы и русские буквы.
- Писать значения строчными буквами.
- Не менять название одной кампании от ссылки к ссылке.
- Не включать в UTM персональные данные клиента.
- Не использовать телефон, имя клиента, адрес объекта или сведения о доходе.

Хорошо:

```text
utm_campaign=family_mortgage_july
```

Плохо:

```text
utm_campaign=Семейная ипотека июль Татьяна
```

## 3. Рекомендуемые значения `utm_source`

| Источник | Значение |
|---|---|
| Личная страница ВКонтакте | `vk_profile` |
| Сообщество ВКонтакте | `vk_community` |
| Таргетированная реклама ВКонтакте | `vk_ads` |
| Городская группа ВКонтакте | `vk_city_group` |
| Объявление на Авито | `avito` |
| Telegram-канал | `telegram` |
| MAX | `max` |
| QR-код на листовке | `qr_flyer` |
| QR-код на визитке | `qr_business_card` |
| QR-код в офисе | `qr_office` |
| Наружная реклама | `outdoor` |
| Партнер или риелтор | `partner` |
| Email | `email` |

## 4. Рекомендуемые значения `utm_medium`

| Формат | Значение |
|---|---|
| Обычный пост | `social_post` |
| Платная реклама | `paid_social` |
| Ссылка в профиле | `profile_link` |
| Ссылка в сообществе | `community_link` |
| Объявление | `classified` |
| Сообщение в мессенджере | `messenger` |
| QR-код | `qr` |
| Печатная реклама | `print` |
| Партнерская рекомендация | `referral` |
| Email-рассылка | `email` |

## 5. Названия кампаний

Рекомендуемый формат:

```text
тема_география_период
```

Примеры:

```text
general_borisoglebsk_2026_07
family_mortgage_borisoglebsk_2026_07
mortgage_denied_borisoglebsk_2026_07
house_mortgage_gribanovskiy_2026_07
etagi_clients_borisoglebsk_2026_07
```

Кампанию можно оставлять без месяца, если ссылка используется долго:

```text
business_card_main
vk_profile_permanent
office_qr_permanent
```

## 6. Примеры готовых ссылок

### Личная страница ВКонтакте

```text
https://sterlikova-ipoteka.ru/?utm_source=vk_profile&utm_medium=profile_link&utm_campaign=vk_profile_permanent
```

### Пост о семейной ипотеке

```text
https://sterlikova-ipoteka.ru/uslugi/semeynaya-ipoteka/?utm_source=vk_community&utm_medium=social_post&utm_campaign=family_mortgage_borisoglebsk_2026_07&utm_content=post_01
```

### Реклама после отказа банка

```text
https://sterlikova-ipoteka.ru/uslugi/otkazali-v-ipoteke/?utm_source=vk_ads&utm_medium=paid_social&utm_campaign=mortgage_denied_borisoglebsk_2026_07&utm_content=creative_01
```

### QR-код на визитке

```text
https://sterlikova-ipoteka.ru/konsultaciya/?utm_source=qr_business_card&utm_medium=qr&utm_campaign=business_card_main
```

### QR-код на листовке по домам

```text
https://sterlikova-ipoteka.ru/uslugi/ipoteka-na-dom/?utm_source=qr_flyer&utm_medium=print&utm_campaign=house_mortgage_borisoglebsk_2026_07&utm_content=flyer_a4_01
```

### Размещение в городской группе

```text
https://sterlikova-ipoteka.ru/konsultaciya/?utm_source=vk_city_group&utm_medium=social_post&utm_campaign=general_borisoglebsk_2026_07&utm_content=group_name_post_01
```

## 7. Выбор целевой страницы

Не отправлять весь рекламный трафик только на главную.

- Общая реклама брокера → `/` или `/konsultaciya/`.
- Семейная ипотека → `/uslugi/semeynaya-ipoteka/`.
- Материнский капитал → `/uslugi/materinskiy-kapital/`.
- Отказ банка → `/uslugi/otkazali-v-ipoteke/`.
- Покупка дома → `/uslugi/ipoteka-na-dom/`.
- Строительство дома → `/uslugi/ipoteka-na-stroitelstvo-doma/`.
- ИП и самозанятые → `/uslugi/ipoteka-dlya-ip-samozanyatyh/`.
- Нет официального дохода → `/uslugi/ipoteka-bez-oficialnogo-dohoda/`.
- Покупка в конкретном городе или районе → соответствующая страница `/geo/`.

Целевая страница должна соответствовать обещанию рекламного объявления.

## 8. Использование в QR-кодах

Перед печатью QR-кода:

1. Открыть итоговую UTM-ссылку в браузере.
2. Проверить, что страница загружается по HTTPS.
3. Проверить все параметры после знака `?`.
4. Создать QR-код только после проверки ссылки.
5. Отсканировать QR-код с двух разных телефонов.
6. Сохранить исходную ссылку рядом с макетом в рабочем архиве.

Для каждого тиража или макета желательно использовать отдельное значение `utm_content`.

## 9. Таблица учета рекламных ссылок

Для работы достаточно таблицы со столбцами:

- дата создания;
- кампания;
- площадка;
- целевая страница;
- полная UTM-ссылка;
- `utm_source`;
- `utm_medium`;
- `utm_campaign`;
- `utm_content`;
- где размещена ссылка;
- дата окончания размещения;
- ответственный;
- примечание.

## 10. Проверка после подключения Метрики

После добавления ID Яндекс Метрики проверить:

- сохраняются ли UTM-параметры при открытии страницы;
- появляется ли источник в отчетах Метрики;
- фиксируются ли цели `phone_click`, `vk_click`, `max_copy`, `consultation_click`, `contacts_click`, `calculator_input`;
- можно ли связать цель с конкретной кампанией и макетом;
- не используются ли разные названия одной кампании.

## 11. Запрещенные практики

- Не сокращать UTM-ссылки неизвестными сервисами перед печатью важных материалов.
- Не использовать одну и ту же ссылку для всех рекламных каналов.
- Не менять регистр символов внутри одной кампании.
- Не добавлять в параметры ФИО, телефон или финансовые данные клиента.
- Не вести рекламу на страницу, которая не соответствует тексту объявления.
