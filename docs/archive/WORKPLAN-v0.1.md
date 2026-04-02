# Synapse Workplan (v0.1)

Дата: 2026-03-31  
Рабочее имя SDK: `synapse-sdk`

## 1) Product Goal

Сделать Synapse "cognitive state layer" для AI-агентов:
- агенты генерируют наблюдения и факты;
- Synapse синтезирует их в черновики знаний;
- человек подтверждает/правит;
- подтвержденные знания мгновенно доступны всем агентам через MCP.

## 2) Что значит "универсальный OSS SDK"

`synapse-sdk` должен быть:
1. Framework-agnostic: работает с LangGraph, CrewAI, AutoGen, Haystack и "чистыми" агентами без жесткой привязки.
2. Transport-agnostic: HTTP по умолчанию + возможность кастомного транспорта (self-hosted, air-gapped).
3. Provider-agnostic: OpenAI/Anthropic/local LLM через единый формат событий и claim-модель.
4. Local-first: можно запускать полностью локально без облака.
5. Extensible: интеграции и экстракторы оформлены как плагины.
6. Stable API: четкое versioning policy (`v1` event schema + semver).
7. OSS-first: открытые контракты, документация, примеры, без vendor lock-in.

## 3) Техническая рамка SDK

## 3.1 Core contract (общий для Python/TS)

Стабильные сущности:
- `ObservationEvent`
- `Claim`
- `EvidenceRef`
- `Conflict`
- `KnowledgeUpdate`

Базовые API:
- `init(config)`
- `monitor(agent_or_runner, options?)`
- `capture(event)`
- `propose_fact(input)`
- `flush()`

## 3.2 Adapter model

Слои:
1. `core`: типы, валидация, retry, batching, idempotency keys.
2. `integrations/*`: адаптеры под фреймворки (LangGraph, CrewAI, AutoGen).
3. `extractors/*`: извлечение claims из tool outputs/диалогов.
4. `transports/*`: HTTP/stdout/file queue/custom.

## 3.3 Safety + governance by design

- PII redaction hooks до отправки событий.
- Source traceability: каждый claim имеет ссылки на evidence.
- Human approval gate для критичных категорий.
- TTL/staleness policy для устаревающих фактов.

## 4) Архитектура платформы (MVP)

1. `services/api` (FastAPI): ingestion + query API.
2. `services/worker`: synthesis pipeline (extract -> dedup -> conflict -> draft).
3. `services/mcp`: MCP server для runtime контекста.
4. `apps/web`: review UI (approve/edit/reject + semantic diff).
5. `infra/postgres`: claims/events/page versions + pgvector.

## 5) План работ (8 недель)

## Фаза 1 (Недели 1-2): Foundation

Цель: запустить ingest end-to-end.
- Описать `v1` event schema и claim schema.
- Поднять `services/api` + Postgres.
- Сделать `synapse-sdk` core (Python + TS skeleton).
- Реализовать `capture()` и `propose_fact()` с idempotency и retries.
- Добавить локальный запуск через docker-compose.

DoD:
- событие от SDK попадает в БД;
- есть e2e smoke-test;
- есть quickstart "за 3 команды".

## Фаза 2 (Недели 3-4): Synthesis Engine

Цель: из сырых событий получить Draft Knowledge.
- Extraction pipeline (rule-based + LLM fallback).
- Deduplication и clustering.
- Conflict detector (новый claim vs published claim).
- Генерация `draft_pages` в Markdown.

DoD:
- из 100 событий формируются структурированные drafts;
- конфликты видны в системе с evidence links.

## Фаза 3 (Недели 5-6): Human-in-the-loop UI

Цель: дать бизнесу контроль без кода.
- Inbox черновиков.
- Approve / Edit / Reject flow.
- Semantic diff для "было -> стало".
- Audit trail (кто/когда/почему).

DoD:
- подтвержденный draft публикуется в knowledge snapshot;
- полный trace от факта до решения редактора.

## Фаза 4 (Недели 7-8): Runtime via MCP

Цель: knowledge становится "прошивкой" агентов.
- MCP tools: `search_knowledge`, `get_entity_facts`, `get_recent_changes`.
- Context injection helper в SDK.
- Cache + invalidation на publish.
- Базовые метрики качества.

DoD:
- агент получает новое знание в следующем запросе после approve;
- latency publish -> retrieval <= 5s (целевое).

## 6) OSS package strategy

Репозиторий (monorepo):
- `packages/synapse-sdk-ts`
- `packages/synapse-sdk-py`
- `packages/synapse-schema`
- `services/api`
- `services/worker`
- `services/mcp`
- `apps/web`

Публикация:
- TS: npm (`@synapse/sdk`)
- Python: PyPI (`synapse-sdk`)
- Общая схема: JSON Schema + generated types.

Лицензирование:
- Core: Apache-2.0 (рекомендуется).
- Enterprise add-ons: отдельные приватные модули.

## 7) KPI для MVP

1. Time-to-integrate SDK: < 10 минут.
2. Time event -> draft: < 60 секунд.
3. Time approve -> MCP available: < 5 секунд.
4. Доля одобренных draft'ов без ручной правки: >= 50% на пилоте.
5. Снижение ошибок от устаревших знаний: >= 30% на пилоте.

## 8) Риски и как их снять

1. Шумные факты и ложные claims.
   - Митигация: confidence scoring + quorum по источникам + mandatory evidence.
2. Конфликты знаний во времени.
   - Митигация: temporal fields (`valid_from`, `valid_to`) и TTL policy.
3. Сложность интеграций.
   - Митигация: минимальный universal API + adapters как плагины.
4. Vendor lock-in опасения у OSS-сообщества.
   - Митигация: open schema, local mode, export/import snapshots.

## 9) Ближайшие next tasks (backlog)

1. Утвердить `v1` schemas (`ObservationEvent`, `Claim`, `DraftPage`).
2. Создать структуру монорепо.
3. Сделать Python/TS hello-world SDK examples.
4. Реализовать ingestion API + миграции БД.
5. Добавить e2e demo: "Omega gate access card" кейс.
6. Подготовить public README с Quick Start.

## 10) Governance: актуальность Roadmap

Источник правды по статусам: `ROADMAP.md`  
Протокол:
1. После каждого внедрения обновить статус соответствующего milestone/task в `ROADMAP.md`.
2. Добавить запись в раздел `Recent Updates` с датой и кратким итогом.
3. Если внедрение меняет приоритеты, обновить `Next Up`.
4. Если внедрение открывает новый риск, добавить его в `Risks to Watch`.

Definition of Done для каждой задачи расширяется:
- код/изменение внедрено;
- базовая проверка пройдена;
- roadmap обновлен и отражает текущее состояние.
