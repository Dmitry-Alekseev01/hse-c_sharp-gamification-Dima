# hse-c_sharp-gamification

Курсовая работа НИУ ВШЭ, 3 курс, «Программная инженерия».

## Dev launch through Nginx

В корне репозитория добавлен общий `docker-compose.yml`, который поднимает:
- `frontend`
- `backend`
- `postgres`
- `redis`
- `worker`
- `nginx`

Запуск:

```bash
docker compose up --build
```

Точки входа:
- фронтенд через nginx: `http://localhost:8080`
- backend API через nginx: `http://localhost:8080/api/v1/...`
- healthcheck: `http://localhost:8080/health/live`
- swagger: `http://localhost:8080/docs`

Для связки фронта и бэка лучше использовать относительные пути:

```js
fetch("/api/v1/materials")
```

Тогда фронтенду не нужно знать прямой адрес backend-контейнера или отдельный localhost-порт.
