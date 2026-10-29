# Виртуальное Казино — статическая версия для GitHub Pages

Эта ветка (`gh-pages`) содержит только сайт для GitHub Pages. Исходный Flask-проект находится в ветке `main`.

Сервера здесь нет: логика игр работает в браузере на JavaScript, а пользователи, баланс,
история транзакций и настройки игр хранятся в `localStorage`. У каждого посетителя свои данные,
и они не синхронизируются между браузерами и устройствами.

Демо-администратор: `admin` / `admin`.

## Публикация

Settings → Pages → Build and deployment → Source: **Deploy from a branch**,
Branch: **gh-pages**, папка **/ (root)**.

## Локальный запуск

```bash
python -m http.server 8000
```

Затем откройте http://localhost:8000

## Структура

```
index.html, login.html, register.html, profile.html  — основные страницы
slots.html, roulette.html, crash.html, mines.html     — игры
admin*.html                                            — админ-панель
js/store.js   — хранилище (пользователи, баланс, транзакции, конфиги)
js/layout.js  — навбар, пополнение через рекламу, проверка доступа
css/style.css — стили
ad/           — рекламные видео
```
