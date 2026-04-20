# AI-геймификация заданий (Backend)

Документ описывает, как в проекте работает AI-геймификация, зачем она нужна, какие ограничения соблюдаются и как безопасно эксплуатировать фичу.

## 1. Цель

AI-геймификация нужна, чтобы:
- переписывать скучный текст задания в более вовлекающий формат;
- добавлять сюжетный контекст и культурные отсылки (например, аниме-сеттинг);
- при этом **не менять учебную суть задания**.

Ключевой принцип: AI меняет форму подачи, но не меняет проверяемую логику.

## 2. Что именно делает фича

Система работает как асинхронный pipeline:
1. Преподаватель/админ отправляет запрос на геймификацию.
2. Backend создаёт `job` со статусом `pending`.
3. Worker берёт job из Redis-очереди и вызывает LLM (OpenRouter).
4. AI-черновик сохраняется как `completed` (или `failed` при ошибке).
5. Преподаватель вручную применяет черновик к `material` или `question`.

Важно: автопубликации нет, финальное применение всегда явное (`/apply`).

## 3. Бизнес-правила промпта

Промпт настроен на задачу “сделать интереснее, но не исказить смысл”:
- стилизация в геймифицированный/аниме-формат;
- сохранение всех числовых значений (лимиты, баллы, проценты, дедлайны и т.д.);
- сохранение логики, критериев и ограничений задания;
- запрет на добавление новых требований “от себя”.

### Выбор вселенной (аниме)

Сейчас поддерживаются подсказки через `constraints`:
- `anime: Naruto`
- `anime: Bleach`
- `anime: Jujutsu Kaisen` (или “Магическая Битва”)

Если явного предпочтения нет, используется дефолтный сеттинг.

## 4. Роли и доступ

- `teacher`, `admin`:
  - могут создавать job;
  - читать свои job (admin видит все);
  - применять draft;
  - ретраить failed job.
- `admin`:
  - дополнительно видит ops-метрики (`/api/v1/ai/ops/metrics`).
- `user`:
  - не имеет доступа к AI-геймификации.

## 5. API (основные endpoints)

Базовый префикс: `/api/v1/ai`

- `POST /gamify`  
  Создаёт асинхронный job, ответ: `202 Accepted`.

- `GET /gamify`  
  Листинг job с фильтрами (`status`, `source_type`, `limit`, `offset`).

- `GET /gamify/{job_id}`  
  Получение статуса/результата конкретного job.

- `POST /gamify/{job_id}/apply`  
  Применение готового draft к `material` или `question`.

- `POST /gamify/{job_id}/retry`  
  Ретрай только для job в статусе `failed`.

- `GET /ops/metrics`  
  Операционные метрики AI-пайплайна (только admin).

Полный контракт и схемы: `Backend/docs/api-contract.yaml`.

## 6. Жизненный цикл job

Статусы:
- `pending` -> создан и ждёт обработки;
- `running` -> worker обрабатывает;
- `completed` -> draft готов, можно review/apply;
- `failed` -> генерация не удалась после retry-политики;
- `applied` -> draft применён к целевой сущности.

Повторное применение:
- идемпотентно, если target тот же;
- `409 Conflict`, если пытаются применить уже `applied` job в другой target.

## 7. Надёжность и отказоустойчивость

### 7.1 Очередь и retry

- Redis queue: `ai:gamify`
- retry-счётчик: `ai:gamify:retry:{job_id}`
- dead-letter queue: `ai:gamify:dlq`

Если генерация падает:
- worker увеличивает счётчик;
- если лимит не исчерпан, requeue;
- иначе job переводится в `failed` и пишется в DLQ.

### 7.2 Semantic fallback

Даже если LLM вернул валидный JSON, backend дополнительно проверяет смысловую полноту:
- `draft_title`, `story_frame`, `task_goal` не должны быть пустыми/слишком короткими.

Если первичный ответ “пустой”:
- выполняется один fallback-вызов с усиленным constraint;
- если fallback тоже плохой, дальше обычная retry/fail логика.

## 8. Метрики эксплуатации

`GET /api/v1/ai/ops/metrics` возвращает:
- `queued_jobs`
- `dead_letter_jobs`
- `jobs_processed`
- `jobs_completed`
- `jobs_failed`
- `jobs_retried`
- `jobs_semantic_fallback_used`

Практический смысл:
- рост `jobs_failed`/`dead_letter_jobs` -> проблемы провайдера/промпта;
- рост `jobs_semantic_fallback_used` -> модель всё чаще отдаёт слабые черновики;
- высокий `queued_jobs` при стабильной нагрузке -> worker не успевает.

## 9. Конфигурация (ENV)

Основные переменные:
- `AI_GAMIFICATION_ENABLED`
- `AI_GAMIFICATION_DAILY_QUOTA_PER_USER`
- `AI_GAMIFICATION_MAX_SOURCE_CHARS`
- `AI_GAMIFICATION_JOB_MAX_RETRIES`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `OPENROUTER_MODEL`
- `OPENROUTER_FALLBACK_MODELS`
- `OPENROUTER_TIMEOUT_SECONDS`
- `OPENROUTER_MAX_RETRIES`
- `OPENROUTER_SITE_URL`
- `OPENROUTER_APP_NAME`

См. шаблон: `Backend/.env.example`.

## 10. Безопасность и ограничения

- Доступ к endpoint ограничен ролями.
- Применение draft к “чужим” сущностям блокируется ACL-проверками.
- Для `source_type=material/question` применяется привязка source->target (нельзя применить в случайный target).
- Включены rate-limit и дневная квота на создание AI-job.
- Источник текста ограничивается по длине (`AI_GAMIFICATION_MAX_SOURCE_CHARS`).

## 11. Быстрый e2e сценарий проверки

1. Логин teacher/admin.
2. `POST /api/v1/ai/gamify` с `source_type=raw_text`.
3. Поллинг `GET /api/v1/ai/gamify/{job_id}` до `completed/failed`.
4. Если `completed`, `POST /apply`.
5. Проверка изменённой `material`/`question`.
6. Для admin: проверка `/api/v1/ai/ops/metrics`.

## 12. Типовые ошибки и диагностика

- `503 AI gamification is disabled`  
  Не включён feature flag.

- `503 OPENROUTER_API_KEY is required`  
  Не задан API-ключ.

- `429 Daily AI quota exceeded`  
  Превышена дневная квота пользователя.

- `409 Job must be completed before apply`  
  Попытка apply до завершения job.

- `409 AI draft is semantically empty: ...`  
  Ответ модели не прошёл semantic quality gate.

- `409 Only failed jobs can be retried`  
  Ретрай возможен только для `failed`.

## 13. Что важно помнить команде

- Фича не должна превращаться в “автогенерацию нового задания”.
- Проверяемая учебная логика всегда первична.
- AI-пайплайн должен быть наблюдаемым (метрики), воспроизводимым (job history) и безопасным (role/ACL/quota).
