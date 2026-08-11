# AI Cooking Assistant

Учебный MVP Telegram-бота, который превращает текст, голос, фотографию ингредиентов или фотографию готового блюда в структурированные рецепты. Бот использует OpenAI для генерации текста, анализа изображений и распознавания речи, сохраняет рецепты в SQLite и поддерживает форму Telegram Mini App.

## Что умеет проект

- по списку продуктов предлагает три блюда;
- по фотографии ингредиентов определяет продукты и предлагает три рецепта;
- по фотографии готового блюда определяет его и восстанавливает рецепт;
- переводит голосовое сообщение в текст и обрабатывает его как обычный запрос;
- в режиме `/chef` задаёт до трёх уточняющих вопросов;
- сохраняет каждый сгенерированный рецепт в SQLite;
- переключает признак «избранное» по inline-кнопке;
- принимает расширенный запрос из Telegram Mini App.

## Два режима без изменения кода

Проект специально настроен так, чтобы локальная разработка и будущее серверное размещение использовали один и тот же `bot.py`:

| Режим | `ENABLE_NGROK` | `WEBAPP_URL` | Что происходит |
|---|---:|---|---|
| Локальный, рекомендуемый сейчас | `true` | пусто | `python bot.py` запускает бота, aiohttp и ngrok в одном процессе |
| Серверный | `false` | постоянный `https://...` | `python bot.py` запускает бота и aiohttp; HTTPS предоставляет сервер/reverse proxy |
| Локальный без Mini App | `false` | пусто | текст, голос, фото и `/chef` работают; кнопка Mini App скрыта |

Таким образом, при переезде на сервер переписывать Python-код не потребуется: достаточно изменить переменные окружения и настроить HTTPS-прокси.

## Как проходит запрос

```text
Пользователь Telegram
        │
        ▼
handlers/ — определение сценария и проверка входа
        │
        ├── текст/форма ───────────────┐
        ├── голос → транскрипция ──────┤
        └── фото → JPEG data URI ──────┤
                                       ▼
                         services/recipe_generator.py
                         prompt → OpenAI → JSON
                                       │
                                       ▼
                         services/recipes/schemas.py
                         проверка и нормализация JSON
                                       │
                         ┌─────────────┴─────────────┐
                         ▼                           ▼
                  SQLite recipes.db           сообщение Telegram
```

Aiogram получает события методом long polling. `DependencyMiddleware` в `bot.py` передаёт обработчикам общие сервисы, поэтому API-клиент, память и репозиторий не создаются заново для каждого сообщения.

## Структура проекта

```text
project/
├── bot.py                       # запуск бота, middleware и HTTP-сервера
├── config.py                    # чтение и проверка переменных окружения
├── .env.example                 # безопасный шаблон настроек
├── requirements.txt             # Python-зависимости
├── handlers/                    # входящие события Telegram
│   ├── start.py                 # /start, /help, /miniapp
│   ├── text_recipe.py           # общий текстовый конвейер
│   ├── voice_recipe.py          # голос → текст → общий конвейер
│   ├── image_ingredients.py     # загрузка фото и выбор режима
│   ├── dish_identify.py         # фото готового блюда
│   ├── interactive_flow.py      # FSM-диалог /chef
│   ├── webapp_data.py           # JSON от Mini App
│   └── favorites.py             # кнопка избранного
├── services/
│   ├── openai_client.py         # адаптер OpenAI SDK
│   ├── recipe_generator.py      # prompt-шаблоны
│   ├── interactive_chef.py      # логика шага /chef
│   ├── memory.py                # короткая история в RAM
│   ├── ngrok_tunnel.py          # временный HTTPS для локального Mini App
│   ├── storage.py               # запросы SQLite
│   └── recipes/schemas.py       # RecipeData и разбор JSON
├── utils/                       # аудио, изображения и вывод рецепта
└── miniapp/                     # HTML, JavaScript и CSS формы
```

`recipes.db` — локальная база данных. Она не нужна для первого запуска: если файла нет, приложение создаст его и таблицу автоматически. Папки `__pycache__` также создавать или переносить не нужно.

## Требования

- Python 3.10 или новее (рекомендуется 3.11/3.12);
- Telegram-аккаунт и токен бота от `@BotFather`;
- API-ключ OpenAI с доступом к выбранным моделям;
- бесплатный аккаунт ngrok и authtoken для локального запуска Mini App;
- интернет для Telegram и OpenAI;
- публичный HTTPS-адрес для Mini App — его временно выдаёт ngrok либо постоянно предоставляет сервер.

Для текстовых, голосовых и фото-сценариев отдельные FFmpeg или системные аудиодрайверы не требуются: бот принимает уже записанное сообщение Telegram и передаёт его байты API.

## Установка на Windows

Откройте PowerShell в папке `project`.

1. Создайте виртуальное окружение:

   ```powershell
   py -m venv .venv
   ```

2. Активируйте его:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   Если PowerShell запрещает выполнение скрипта, разрешите его только для текущего окна:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

3. Обновите pip и установите зависимости:

   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Создайте рабочий `.env` из шаблона:

   ```powershell
   Copy-Item .env.example .env
   ```

5. Откройте `.env` и замените примеры токена OpenAI, Telegram и ngrok настоящими значениями. Для текущего локального режима оставьте:

   ```dotenv
   WEBAPP_HOST=127.0.0.1
   WEBAPP_PORT=8080
   ENABLE_NGROK=true
   NGROK_AUTHTOKEN=ваш_токен_ngrok
   WEBAPP_URL=
   ```

6. Запустите проект:

   ```powershell
   python bot.py
   ```

В журнале появятся две важные строки:

```text
Публичный адрес Mini App: https://....ngrok-free.app
Bot started. Waiting for updates...
```

После них откройте бота в Telegram и отправьте `/start`. Отдельно запускать `ngrok.exe`, HTML-сервер или второй терминал не нужно.

## Установка на Linux или macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`, затем выполните:

```bash
python bot.py
```

## Настройка Telegram и OpenAI

### Токен Telegram

1. Откройте в Telegram официального `@BotFather`.
2. Выполните `/newbot` и задайте имя и username.
3. Скопируйте токен в `TELEGRAM_BOT_TOKEN`.
4. Не публикуйте `.env` и не отправляйте токен в репозиторий.

### Ключ OpenAI

Создайте API-ключ в своей учётной записи OpenAI и поместите его в `OPENAI_API_KEY`. Подписка ChatGPT и биллинг API являются отдельными продуктами: для API должен быть настроен доступ и лимит расходов.

Модели задаются отдельно:

| Переменная | Для чего используется | Значение по умолчанию |
|---|---|---|
| `OPENAI_TEXT_MODEL` | текст и интерактивный шеф | `gpt-4o-mini` |
| `OPENAI_VISION_MODEL` | анализ фотографий | `gpt-4o-mini` |
| `OPENAI_TRANSCRIBE_MODEL` | распознавание голосовых | `gpt-4o-mini-transcribe` |

Если модель недоступна вашему API-проекту, замените значение на совместимую модель. После изменения `.env` перезапустите бота: настройки кэшируются на время процесса.

## Переменные окружения

| Переменная | Обязательна | Назначение |
|---|---:|---|
| `TELEGRAM_BOT_TOKEN` | да | секретный токен Telegram-бота |
| `OPENAI_API_KEY` | да | секретный ключ OpenAI API |
| `OPENAI_TEXT_MODEL` | нет | модель текстовой генерации |
| `OPENAI_VISION_MODEL` | нет | модель с поддержкой изображений |
| `OPENAI_TRANSCRIBE_MODEL` | нет | модель транскрипции |
| `WEBAPP_HOST` | нет | интерфейс локального HTTP-сервера; обычно `127.0.0.1` |
| `WEBAPP_PORT` | нет | локальный порт; по умолчанию `8080` |
| `ENABLE_NGROK` | нет | `true` автоматически запускает туннель для локальной работы |
| `NGROK_AUTHTOKEN` | при включённом ngrok | секретный токен аккаунта ngrok |
| `WEBAPP_URL` | для сервера | постоянный публичный HTTPS URL формы; в auto-ngrok остаётся пустым |
| `WEBAPP_STATIC_DIR` | нет | папка со статикой Mini App |
| `DATABASE_PATH` | нет | путь к SQLite-файлу |

Пути в `config.py` преобразуются в абсолютные. Чтобы избежать зависимости от текущей папки, запускайте `python bot.py` из корня проекта либо укажите абсолютные пути.

## Почему Mini App требует HTTPS

При запуске `bot.py` aiohttp раздаёт:

- `/` → `miniapp/index.html`;
- `/static/` → CSS и JavaScript из `miniapp/`.

Для проверки только внешнего вида формы в браузере откройте `http://127.0.0.1:8080`. В обычном браузере Telegram API отсутствует, поэтому submit работает в демонстрационном режиме: JSON выводится в консоль разработчика и показывается alert.

Telegram Bot API требует, чтобы `WebAppInfo.url` был HTTPS URL. Адрес `http://127.0.0.1:8080` доступен только на компьютере разработчика и не подходит Telegram на телефоне. Покупка собственного домена и ручная настройка SSL нужны для постоянного production-адреса, но не для локального MVP: ngrok выдаёт временный HTTPS URL и завершает TLS вместо приложения.

## Локальный запуск с автоматическим ngrok — рекомендуемый вариант

### 1. Получите authtoken

1. Зарегистрируйтесь на сайте ngrok.
2. Откройте раздел с вашим authtoken в личном кабинете.
3. Скопируйте только значение токена, без команды `ngrok config ...`.
4. Вставьте его в локальный `.env`:

   ```dotenv
   ENABLE_NGROK=true
   NGROK_AUTHTOKEN=ваш_длинный_токен
   WEBAPP_URL=
   ```

`.env` уже исключён из Git. Не помещайте настоящий authtoken в `.env.example`, README, скриншоты или публичный репозиторий.

### 2. Выполните одну команду

```powershell
python bot.py
```

В одном процессе последовательно запускаются:

1. локальный HTTP-сервер aiohttp на `127.0.0.1:8080`;
2. ngrok agent, который направляет временный HTTPS URL на этот порт;
3. Telegram long polling.

Полученный URL автоматически записывается в объект настроек в памяти. Команды `/start` и `/miniapp` сразу создают кнопку с актуальным адресом — копировать URL из консоли в `.env` и перезапускать бота не требуется.

### 3. Проверьте полный сценарий

1. Не закрывая PowerShell, отправьте боту `/start`.
2. Нажмите `🚀 Mini App`.
3. Заполните продукты и отправьте форму.
4. Telegram закроет форму и передаст JSON тому же боту.
5. Бот сгенерирует и сохранит рецепты.

### Что важно понимать про бесплатный локальный туннель

- проект работает только пока включён компьютер, есть интернет и запущен `python bot.py`;
- после `Ctrl+C`, сна, перезагрузки или потери сети бот и Mini App становятся недоступны;
- адрес ngrok может измениться при следующем запуске, но код подставит новый адрес автоматически;
- туннель публикует форму в интернете, поэтому не добавляйте в папку `miniapp` секретные файлы;
- текстовые, голосовые и фото-функции бота используют Telegram polling и сами по себе не требуют ngrok; туннель нужен именно для Mini App;
- это режим тестирования, а не непрерывный production-хостинг.

### Альтернатива: ngrok отдельной командой

Автоматический режим удобнее, но при диагностике можно отключить его:

```dotenv
ENABLE_NGROK=false
WEBAPP_URL=https://адрес-из-ngrok
```

Затем в первом терминале запустите проект, а во втором — установленный ngrok CLI:

```powershell
ngrok http 8080
```

Скопируйте выданный HTTPS URL в `WEBAPP_URL` и перезапустите `bot.py`. Этот вариант требует двух процессов и ручного обновления адреса, поэтому для обычного занятия он не рекомендуется.

## Размещение на сервере в будущем

На сервере ngrok не нужен. Код уже готов к постоянному URL: aiohttp продолжает раздавать Mini App, а Nginx или Caddy принимает HTTPS-запросы и перенаправляет их на локальный порт приложения.

### Что понадобится

- VPS или другой постоянно работающий Linux-сервер;
- домен или поддомен, например `cook.example.com`;
- DNS A/AAAA-запись домена на IP сервера;
- HTTPS reverse proxy — ниже показан Nginx;
- SSL-сертификат, например бесплатный Let’s Encrypt;
- systemd для автоматического старта и перезапуска бота.

Вместо VPS можно использовать облачную платформу, которая сама выдаёт HTTPS-домен и запускает Python-процесс. Тогда пропустите Nginx/Certbot и задайте выданный платформой URL в `WEBAPP_URL`.

### 1. Подготовьте приложение

На Ubuntu/Debian установите Python, venv, Nginx и Certbot:

```bash
sudo apt update
sudo apt install -y python3 python3-venv nginx certbot python3-certbot-nginx
```

Скопируйте проект, например в `/opt/ai-cooking-assistant`, и установите зависимости:

```bash
cd /opt/ai-cooking-assistant
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

### 2. Создайте серверный `.env`

```dotenv
TELEGRAM_BOT_TOKEN=реальный_токен
OPENAI_API_KEY=реальный_ключ
OPENAI_TEXT_MODEL=gpt-4o-mini
OPENAI_VISION_MODEL=gpt-4o-mini
OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe

WEBAPP_HOST=127.0.0.1
WEBAPP_PORT=8080
WEBAPP_STATIC_DIR=/opt/ai-cooking-assistant/miniapp
WEBAPP_URL=https://cook.example.com

ENABLE_NGROK=false
NGROK_AUTHTOKEN=
DATABASE_PATH=/opt/ai-cooking-assistant/data/recipes.db
```

`WEBAPP_HOST=127.0.0.1` безопаснее, чем `0.0.0.0`: порт 8080 будет доступен только Nginx на том же сервере. Создайте каталог БД и ограничьте доступ:

```bash
sudo mkdir -p /opt/ai-cooking-assistant/data
sudo chown -R www-data:www-data /opt/ai-cooking-assistant
sudo chmod 600 /opt/ai-cooking-assistant/.env
```

### 3. Создайте systemd-сервис

Файл `/etc/systemd/system/ai-cooking-assistant.service`:

```ini
[Unit]
Description=AI Cooking Assistant Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/ai-cooking-assistant
ExecStart=/opt/ai-cooking-assistant/.venv/bin/python /opt/ai-cooking-assistant/bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Активируйте сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-cooking-assistant
sudo systemctl status ai-cooking-assistant
```

Логи смотрятся командой:

```bash
sudo journalctl -u ai-cooking-assistant -f
```

### 4. Настройте Nginx

Создайте `/etc/nginx/sites-available/ai-cooking-assistant`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name cook.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включите конфигурацию и проверьте синтаксис:

```bash
sudo ln -s /etc/nginx/sites-available/ai-cooking-assistant /etc/nginx/sites-enabled/ai-cooking-assistant
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Получите SSL-сертификат

После того как DNS домена указывает на сервер и порт 80 доступен извне:

```bash
sudo certbot --nginx -d cook.example.com
sudo certbot renew --dry-run
```

Certbot изменит Nginx-конфигурацию для HTTPS и настроит автоматическое продление сертификата. Проверьте в браузере `https://cook.example.com`, затем отправьте боту `/miniapp`.

### 6. Обновление проекта на сервере

После загрузки новой версии кода:

```bash
cd /opt/ai-cooking-assistant
./.venv/bin/python -m pip install -r requirements.txt
sudo systemctl restart ai-cooking-assistant
sudo systemctl status ai-cooking-assistant
```

Не запускайте одновременно локальную и серверную копии с одним Telegram-токеном: два polling-процесса будут конкурировать за одни и те же updates.

## Сценарии использования

### Текст

Отправьте, например:

```text
Куриная грудка, брокколи, сливки. Хочу ужин без духовки за 30 минут.
```

Обработчик добавит недавнюю историю, запросит у модели JSON, сохранит рецепты и покажет по одному Telegram-сообщению на рецепт.

### Голос

Запишите голосовое сообщение со списком продуктов. `utils/audio.py` скачает OGG в память, `OpenAIClient.transcribe_audio()` получит текст, после чего будет использован тот же конвейер, что и для печатного сообщения.

### Фото

После фотографии бот просит выбрать:

- «Это ингредиенты» — определить продукты и создать три блюда;
- «Готовое блюдо» — определить блюдо и создать один рецепт с вариациями.

Telegram хранит несколько размеров фото; проект берёт самый большой. Pillow приводит изображение к RGB JPEG качества 90 и кодирует его как base64 data URI.

### Интерактивный шеф

Команда `/chef` переводит чат в FSM-состояние `collecting`. Модель может задать по одному вопросу за шаг, но не более трёх. В этом состоянии обычный текст не попадает в общий текстовый handler. После готового рецепта FSM очищается.

## База данных

Таблица `recipes` создаётся запросом `CREATE TABLE IF NOT EXISTS`. В ней хранятся:

- идентификатор записи и `chat_id`;
- название и время приготовления;
- ингредиенты, шаги, недостающие продукты, вариации и советы как JSON в TEXT;
- источник запроса;
- флаг `is_favorite`;
- время создания.

SQLite подходит для одного процесса и учебного MVP. При горизонтальном масштабировании или интенсивной параллельной записи лучше перейти на PostgreSQL. Файл БД может содержать пользовательские данные, поэтому он добавлен в `.gitignore`; предоставленный демонстрационный `recipes.db` можно удалить перед эксплуатацией.

## Важные архитектурные решения

- `async/await` не блокирует обработку других пользователей во время сетевых запросов.
- Один `OpenAIClient` переиспользуется всеми handler'ами.
- Один `bot.py` запускает polling, aiohttp и при необходимости ngrok; режим выбирается окружением.
- Handler'ы отвечают за Telegram и проверку входа; сервисы — за бизнес-логику; utils — за преобразования.
- Модель обязана вернуть JSON. Парсер удаляет Markdown-ограждения и нормализует поля, но отклоняет ответ без непустого массива `recipes`.
- Текст модели экранируется перед вставкой в Telegram HTML.
- `ConversationMemory` ограничена 12 репликами на чат, чтобы prompt не рос бесконечно.
- FSM и история находятся в RAM и исчезают при рестарте. Рецепты в SQLite сохраняются.

## Проверка проекта без реальных API-запросов

Проверить синтаксис всех Python-файлов:

```bash
python -m compileall -q .
```

Проверить импорт основных модулей после заполнения `.env`:

```bash
python -c "from config import get_settings; print(get_settings())"
python -c "from services.recipes.schemas import parse_recipes_payload; print('Parser import OK')"
```

Минимальная проверка парсера:

```bash
python -c "from services.recipes.schemas import parse_recipes_payload as p; print(p('{\"recipes\":[{\"title\":\"Тест\",\"ingredients\":[],\"steps\":[]}]}'))"
```

## Частые проблемы

### `Отсутствуют обязательные переменные окружения`

Убедитесь, что файл называется именно `.env`, расположен рядом с `bot.py`, а значения `TELEGRAM_BOT_TOKEN` и `OPENAI_API_KEY` не пусты.

### `Unauthorized` от Telegram

Токен неверен, отозван или скопирован с лишними символами. Создайте новый токен через `@BotFather` и перезапустите процесс.

### Ошибка OpenAI или `model_not_found`

Проверьте API-ключ, биллинг, лимиты и доступность всех трёх моделей из `.env`. Названия моделей со временем могут меняться.

### Mini App открывается локально, но не в Telegram

Убедитесь, что `ENABLE_NGROK=true`, в журнале появился адрес `https://...` и окно `python bot.py` остаётся открытым. `127.0.0.1` внутри телефона указывает на сам телефон, а не на компьютер разработчика.

### `ENABLE_NGROK=true, но NGROK_AUTHTOKEN не задан`

Скопируйте authtoken из кабинета ngrok в `.env`. Это не API key и не публичный URL. Если Mini App пока не нужен, поставьте `ENABLE_NGROK=false` и оставьте `WEBAPP_URL` пустым.

### `Не удалось запустить ngrok`

Проверьте интернет, правильность authtoken и отсутствие уже запущенного ngrok agent. Закройте старый процесс, затем запустите `python bot.py` снова. При первом старте pyngrok может загружать agent, поэтому запуск длится дольше обычного.

### Адрес ngrok изменился

Это нормально для временного endpoint. При автоматическом режиме ничего менять не нужно: новый URL уже используется кнопками, созданными после текущего запуска. Откройте новую кнопку через `/start` или `/miniapp`, а не старое сообщение прошлого запуска.

### Кнопка Mini App не появляется

Кнопка появляется, когда есть либо успешный автоматический ngrok, либо непустой `WEBAPP_URL`. Проверьте журнал запуска и вызовите `/start` заново.

### Рецепты исчезли после перезапуска

Сами записи остаются в SQLite, однако текущий интерфейс не реализует команду просмотра сохранённых рецептов. Кнопка меняет флаг в существующем сообщении. История диалога и FSM действительно очищаются при рестарте, поскольку используют RAM.

### Длинный рецепт не отправляется

Telegram ограничивает длину одного сообщения. Сейчас проект не разбивает очень длинный рецепт на части; для production следует добавить безопасное разбиение с сохранением HTML-разметки.

## Ограничения и направления развития

1. Добавить `/favorites` и методы чтения избранного из `RecipeRepository`.
2. Добавить миграции БД: `CREATE TABLE IF NOT EXISTS` не изменяет старую схему.
3. Валидировать размер и MIME-тип пользовательских файлов.
4. Ограничить частоту запросов и максимальную длину текста для контроля затрат.
5. Добавить retry/backoff и тайм-ауты внешних API.
6. Перенести FSM и память в Redis для нескольких процессов и сохранения сессий.
7. Добавить Pydantic/JSON Schema или structured outputs для более строгого ответа модели.
8. Проверять подлинность `initData` Mini App, если форма начнёт обращаться к отдельному backend напрямую.
9. Добавить автоматические тесты handler'ов, prompt-парсера и SQLite-репозитория.
10. Настроить логирование без пользовательских текстов и секретов для production.

## Безопасность

- Никогда не коммитьте `.env` и реальные токены.
- При утечке токена/ключа немедленно отзовите его и создайте новый.
- Считайте текст, JSON Mini App и ответы модели недоверенными данными.
- Не публикуйте `recipes.db`, если в нём есть реальные пользовательские запросы.
- Перед публичным запуском добавьте пользовательское уведомление о передаче текста, фото и голоса внешнему AI-провайдеру.

## Остановка

Нажмите `Ctrl+C`. Блок `finally` в `bot.py` остановит polling, временный ngrok endpoint и HTTP-сервер Mini App. После остановки локальная ссылка перестанет работать — это ожидаемо.
