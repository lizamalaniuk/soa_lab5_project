# Лабораторна робота №5 — Безпека сервісних API

**Дисципліна:** Інформаційні системи на основі сервісів (ІСОС)  
**Тема:** Автентифікація, авторизація та обмеження доступу в мікросервісній системі  
**Проєкт:** Система керування домашніми завданнями (`soa_lab5_project`)

## Мета

Розширити створену в попередніх лабораторних роботах мікросервісну систему механізмами безпеки: налаштувати CORS через API Gateway, реалізувати OAuth 2.0 Authorization Code Flow з PKCE за допомогою Keycloak, перевірку JWT, розмежування доступу за OAuth Scopes та вхід через зовнішнього провайдера Google.

## Архітектура

Система складається з кількох компонентів:

| Компонент | Призначення |
|---|---|
| **Nginx API Gateway** | Єдина точка входу; маршрутизація запитів до мікросервісів |
| **User Service (FastAPI)** | Операції з користувачами; захист створення користувача |
| **Homework Service (FastAPI)** | Операції з домашніми завданнями; перевірка JWT та дозволів |
| **Notification Service (FastAPI)** | Отримання сповіщень |
| **OAuth Service (FastAPI)** | Вхід через Keycloak, обмін authorization code на токени, серверна сесія |
| **Keycloak** | Сервер автентифікації, OAuth 2.0 / OpenID Connect, випуск JWT, брокеризація входу через Google |
| **Redis** | Дані застосунку та короткоживучі OAuth-сесії |
| **RabbitMQ** | Асинхронний обмін повідомленнями |
| **Consumer / Outbox Publisher** | Обробка подій і публікація записів Transactional Outbox |
| **Saga Coordinator / Saga Timeout** | Координація і контроль часу тривалих процесів |
| **A2A Producer** | Компонент агентної взаємодії, доданий у попередній лабораторній |

У репозиторії також зберігаються каталоги `a2a_agents`, `ai_agent` і `mcp_server` з напрацюваннями попередніх лабораторних робіт.

### Схема авторизації

```text
Браузер → Nginx (/oauth/login) → OAuth Service
                              ↓
                        Keycloak (OAuth 2.0 / OIDC)
                              ↔ Google (зовнішній Identity Provider)
                              ↓
                   Authorization Code + PKCE
                              ↓
                       OAuth Service → Redis (сесія)
                              ↓
                    JWT → User / Homework Service
                              ↓
                 Перевірка підпису, issuer, audience,
                         строку дії та scopes
```

## Реалізовані механізми безпеки

### 1. CORS

У трьох FastAPI-сервісах налаштовано `CORSMiddleware` з дозволеним джерелом `https://cad.kpi.ua`. Перевірено preflight-запити `OPTIONS` через Nginx: для User, Homework та Notification Service отримано `HTTP 200` і заголовок `Access-Control-Allow-Origin: https://cad.kpi.ua`.

### 2. OAuth 2.0 Authorization Code Flow + PKCE

У Keycloak створено realm `homework-realm` і клієнт `homework-client`. Використовується **Standard Flow** із **PKCE S256**. OAuth Service створює параметри `state` і `code_verifier`, перенаправляє користувача до Keycloak та обмінює одноразовий код на токени. Access token зберігається в короткоживучій серверній сесії Redis; браузер отримує лише `HttpOnly` session cookie.

### 3. Захист JWT

Спільний модуль `services/auth.py` перевіряє JWT за публічними ключами Keycloak (JWKS), підписом, строком дії, `issuer` та `audience=homework-api`.

- Без токена захищений API повертає **401 Unauthorized**.
- Із дійсним JWT, але без потрібного дозволу, — **403 Forbidden**.
- Із дійсним JWT та потрібним дозволом — успішну відповідь.

### 4. OAuth Scopes

Для клієнта налаштовано *optional* scopes:

| Scope | Призначення | Приклад захищеної операції |
|---|---|---|
| `homework:read` | Читання домашніх завдань | `GET /api/homeworks` |
| `users:write` | Створення користувачів | `POST /api/users` |

OAuth Service підтримує параметр `scope_type`: `basic`, `homework`, `users`. Права перевіряються за полем `scope` у JWT, а не лише за наявністю авторизованого користувача.

### 5. Google Identity Provider

До Keycloak у realm `homework-realm` додано Google як зовнішнього провайдера. Google OAuth-клієнт створюється окремо в Google Auth Platform, а його Redirect URI має вигляд:

```text
http://localhost:8081/realms/homework-realm/broker/google/endpoint
```

Google OAuth Client ID і Client Secret вводяться **в адміністративній панелі Keycloak**; їх **не потрібно записувати в README, комітити до Git або надсилати іншим особам**. Для тестового режиму Google застосунок дозволяє вхід обліковим записам зі списку Test users.

## Структура проєкту

```text
soa_lab5_project/
├── a2a_agents/
├── ai_agent/
├── mcp_server/
├── nginx/
│   └── default.conf
├── services/
│   ├── auth.py
│   ├── oauth.py
│   ├── users.py
│   ├── homework.py
│   ├── notifications.py
│   ├── consumer.py
│   └── ...
├── docker-compose.yml
├── Dockerfile.a2a
├── .gitignore
└── README.md
```

## Запуск

**Передумови:** Docker Desktop із Docker Compose, вільні локальні порти `8080`, `8081`, `9001`, `15672`.

У корені проєкту:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Основні локальні адреси:

| Сервіс | Адреса |
|---|---|
| API Gateway | `http://localhost:8080` |
| Keycloak Admin Console | `http://localhost:8081/admin/` |
| Початок OAuth-входу | `http://localhost:8080/oauth/login` |
| Перевірка OAuth-сесії | `http://localhost:8080/oauth/status` |
| RabbitMQ Management | `http://localhost:15672` |

У **першому** запуску потрібно вручну створити Keycloak realm `homework-realm`, клієнт `homework-client` (Standard Flow, PKCE S256), audience mapper `homework-api`, optional client scopes `homework:read` і `users:write`. Для Google входу додатково налаштувати Google OAuth Client і Google Identity Provider у Keycloak. Дані Keycloak зберігаються в Docker volume `keycloak_data`, тому після звичайного перезапуску повторювати налаштування не потрібно.

### Перевірка OAuth

У браузері відкрий:

- `http://localhost:8080/oauth/login?scope_type=basic` — вхід без додаткових scopes.
- `http://localhost:8080/oauth/login?scope_type=homework` — запит `homework:read`.
- `http://localhost:8080/oauth/login?scope_type=users` — запит `users:write`.
- `http://localhost:8080/oauth/status` — перевірка поточної серверної сесії.

> Маршрути `/oauth/debug-scopes`, `/oauth/test-jwt` та `/oauth/test-homework-jwt` використовувалися лише під час розроблення і видалені з фінальної конфігурації.

### Перевірка CORS

```bash
curl -i -X OPTIONS http://localhost:8080/api/users \
  -H 'Origin: https://cad.kpi.ua' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: Content-Type'
```

Очікується статус `200 OK` та заголовок `access-control-allow-origin: https://cad.kpi.ua`.

### Перевірка доступу без JWT

```bash
curl -i http://localhost:8080/api/homeworks
```

Очікується `401 Unauthorized`.

## Результати проведених перевірок

| Сценарій | Фактичний результат |
|---|---|
| CORS preflight через Nginx до трьох сервісів | `200 OK`, правильний `Access-Control-Allow-Origin` |
| OAuth 2.0 Authorization Code Flow з PKCE | Успішний вхід; `authenticated: true`, `token_present: true` |
| User Service без токена | `401 Unauthorized` |
| User Service з JWT і `users:write` | `201 Created` |
| Homework Service без токена | `401 Unauthorized` |
| Homework Service з JWT без `homework:read` | `403 Forbidden` |
| Homework Service з JWT і `homework:read` | `200 OK` |
| Вхід через Google → Keycloak → OAuth Service | Успішна авторизація та доступ до Homework Service (`200 OK`) |
| Видалений діагностичний маршрут `/oauth/debug-scopes` | `404 Not Found` |

## Зауваження щодо безпеки

Проєкт використовується **лише локально для навчання**. У режимі розробки використано HTTP і Keycloak `start-dev`; це не конфігурація для публічного розгортання. Для реального середовища потрібні HTTPS, захищені cookies (`Secure`), надійні паролі, керування секретами та додаткове посилення контролю доступу. Не публікуйте Google Client Secret, токени, вміст Redis або облікові дані адміністратора. Якщо секрет було розкрито, його необхідно відкликати та випустити новий.

## Висновок

У лабораторній роботі реалізовано та перевірено базові механізми захисту сервісних API: CORS, OAuth 2.0 Authorization Code Flow із PKCE, JWT, розмежування доступу за scopes та федеративний вхід через Google. Результати HTTP-перевірок підтвердили різницю між відсутністю автентифікації (`401`), відсутністю потрібних прав (`403`) та дозволеним доступом (`200` / `201`).
