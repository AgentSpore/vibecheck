# VibeCheck

**AI vibe-analysis от публичных соц-профилей.** Склеивает следы человека с 13 платформ и выдаёт структурированный отчёт: личность, интересы, red/green flags, vibe-score и cartoon-аватар.

```
reddit · github · bluesky · hackernews · mastodon · devto · substack
  instagram · telegram · habr · pikabu · letterboxd · goodreads · steam
```

---

## Что делает

Вставляешь один или несколько username — за 30–60 секунд получаешь:

- **Vibe-score** 0–100 — общий «вайб»
- **Top interests** — 5–10 тем по силе сигнала
- **Personality traits** с конкретными цитатами-доказательствами
- **Red / green flags** — что настораживает vs что внушает доверие
- **Summary** 2–3 абзаца на русском
- **Avatar-spec** — мультяшный аватар (gender, mood, vibe-color, accessories)

Три режима анализа:

| Режим | Что спрашивает LLM |
|---|---|
| 🌈 `vibe` | Общий портрет — характер, интересы, флаги |
| 🪞 `self` | Как тебя видят HR, свидания, клиенты |
| 🎣 `catfish` | Живой человек или фейк / бот / скам |

## Платформы

| Источник | Вход | Что даёт | Авторизация |
|---|---|---|---|
| Reddit | username | RSS постов+комментов | — |
| GitHub | username | Public events API (push, star, issue) | — |
| Bluesky | handle `user.bsky.social` | AT-proto feed | — |
| HackerNews | username | RSS комментариев + submitted | — |
| Habr | username | RSS статей | — |
| Telegram | channel | RSS-бридж | — |
| Mastodon | `@user@instance` | Atom feed | — |
| Dev.to | username | RSS постов | — |
| Substack | subdomain / custom domain | RSS постов | — |
| Pikabu | username | HTML-скрейп `/@user` (DDoS-Guard passthrough) | — |
| Letterboxd | username | RSS ленты фильмов | — |
| Goodreads | numeric user_id | RSS полки `read` | — |
| Steam | SteamID64 | Public profile + games | — |
| Instagram | username (+ опц. session) | curl_cffi mobile mimic | опц. sessionid |

Instagram приватных профилей — через свой `sessionid` cookie (используется one-shot, не сохраняется).

## Архитектура

Layered: **api → services → schemas**.

```
src/vibecheck/
├── api/            # FastAPI controllers (profile.py, health.py)
├── core/           # config, deps (DI), rate_limit
├── services/       # 13 scrapers + profile_analyzer + agent (pydantic-ai)
├── schemas/        # Pydantic DTOs (AnalyzeRequest, VibeReport, SocialPost)
├── static/         # index.html (vanilla JS, zero-build, PWA-ready)
└── main.py         # app factory + SSE route
```

- **Scrape:** все платформы параллельно через `asyncio.gather`, ошибки изолированы (`return_exceptions=True`)
- **LLM:** pydantic-ai + OpenRouter cascade (6 бесплатных моделей в fallback)
- **Stream:** SSE `stage → scraped → done` для прогресс-бара в UI
- **Rate limit:** 5 req/minute по IP через `asyncio.Lock`
- **Security:** `html.escape` на весь LLM output до отправки в UI

## Quick start

```bash
# local dev
cp .env.example .env              # add OPENROUTER_API_KEY
make install                      # uv sync
make dev                          # :8895 + hot reload

# smoke test (no server needed for scrapers)
make smoke

# docker
make docker
```

Открыть `http://localhost:8895` → вставить username → «ПОЕХАЛИ».

### Env vars

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **yes** | — | LLM inference |
| `AGENT_MODEL` | no | `openai/gpt-oss-120b:free` | primary model |
| `FALLBACK_MODELS` | no | 5 free models | cascade on failure |
| `RETRIES_PER_MODEL` | no | `2` | retry budget per model |
| `PORT` | no | `8895` | HTTP listen |

## Экономика

**Модель:** freemium SaaS с pay-per-depth.

| Tier | Месяц | Лимиты | Ответка |
|---|---|---|---|
| Free | $0 | 5 проверок/день, vibe mode only | захват воронки |
| Starter | $9 | 100 проверок, все 3 режима, export PDF | $100 LTV |
| Growth | $29 | 1000 проверок, API доступ, batch-аналитика | $800 LTV |
| Team | $99 | 10 seats, shared history, slack-integration | $3 500 LTV |

**Cost side:** при free-tier LLM cost = $0. На paid tiers каждая проверка ~$0.002 (gpt-oss-120b через OR cache), margin **~97%**. Серверный расход FastAPI singleton с 13 async HTTP клиентами — ~50 MB RAM на instance, 1 vCPU держит 200 RPS.

**LTV / CAC:** при CAC $30 (Twitter/Reddit organic + paid) LTV/CAC = 27x на Growth, 116x на Team.

## TAM / SAM / SOM

- **TAM:** 4.7B активных юзеров соцсетей × 12% интересуется reputation tooling = **$4.2B** (ARPU $7.5/y)
- **SAM:** англо+русскоязычный сегмент с multi-platform footprint (≥2 соцсети) — **$420M**
- **SOM (2 года):** 50K free MAU → 3% paid conversion → 1500 × $29 avg MRR = **$522K ARR**

## ICP

1. **Dating / HR-скрининг** — проверяют match перед встречей
2. **Self-marketing founders** — аудит «как меня видят инвесторы»
3. **Journalists / OSINT** — быстрый персональный профайл из открытых данных
4. **Community managers** — проверка подозрительных участников на фейковость

## Риски и митигации

| Риск | Митигация |
|---|---|
| Платформы блокируют датацентровые IP | 14 источников → одна дыра не ломает продукт; Instagram через curl_cffi TLS mimic |
| LLM-галлюцинации в `evidence` | pydantic structured output + обязательное поле `evidence` с цитатой |
| Privacy пушбэк | обрабатываем только публичные данные; `html.escape` на весь output; нет persistent storage |
| Rate limits со стороны платформ | параллельный scrape + 15s timeout per source; один упавший не валит запрос |

## API

Один основной endpoint.

**`POST /api/analyze`** → SSE stream

```json
{
  "reddit_username": "spez",
  "github_username": "torvalds",
  "pikabu_username": "Zergeich",
  "letterboxd_username": "davidehrlich",
  "mode": "vibe"
}
```

Stream events:

```
data: {"stage": "scraping", "progress": 10, "message": "..."}
data: {"stage": "scraped",  "progress": 40, "message": "Got 53 items..."}
data: {"stage": "done",     "progress": 100, "data": {profile, report}}
```

OpenAPI: `GET /docs`.

## License

MIT.
