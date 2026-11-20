# Flask Blog API

A small REST API for a blog, built with **Flask**, **SQLAlchemy** and **SQLite**,
with JWT authentication and a full **OpenAPI 3.0** specification.

## Features

| Feature | Description |
| --- | --- |
| **Auth** | Register / login with JWT access tokens (Flask-JWT-Extended). |
| **Articles** | Create, read, update and delete articles with automatic slugs. |
| **Categories** | Every article can be filed under one category. |
| **Hashtags** | Many-to-many tags, created automatically when a new hashtag is used. |
| **Comments** | Authenticated users can comment on articles. |
| **Likes** | Authenticated users can like/unlike an article (one like per user). |
| **Public reads** | All `GET` endpoints work without authentication. |
| **OpenAPI** | Hand-written OpenAPI 3.0 document + interactive Swagger UI. |

## Project structure

```
mgl805-flask-api/
├── app/
│   ├── __init__.py         # application factory, error handling, CLI commands
│   ├── config.py           # environment-driven configuration
│   ├── extensions.py       # db / migrate / jwt instances
│   ├── seed.py             # demo data
│   ├── api/                # blueprints (one module per resource)
│   │   ├── auth.py
│   │   ├── articles.py
│   │   ├── categories.py
│   │   ├── tags.py
│   │   ├── comments.py
│   │   ├── likes.py
│   │   └── docs.py         # /docs, /openapi.yaml
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Marshmallow validation & serialization
│   ├── templates/
│   │   └── swagger.html    # Swagger UI page
│   └── utils/helpers.py    # pagination, slugs, current-user helpers
├── openapi.yaml            # OpenAPI 3.0 specification
├── requirements.txt
├── run.py                  # entry point
└── .env.example
```

## Getting started

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the environment
cp .env.example .env              # then edit the secrets

# 4. Create the SQLite database (blog.db) and load demo data
flask --app run.py init-db
flask --app run.py seed

# 5. Run the development server
python run.py                     # http://127.0.0.1:5000
```

| URL | Description |
| --- | --- |
| <http://127.0.0.1:5000/docs> | Interactive Swagger UI |
| <http://127.0.0.1:5000/openapi.yaml> | Raw OpenAPI document |
| <http://127.0.0.1:5000/openapi.json> | OpenAPI document as JSON |
| <http://127.0.0.1:5000/health> | Health check |

## Authentication

1. `POST /api/auth/register` or `POST /api/auth/login` returns an `access_token`.
2. Send it on protected requests:

```http
Authorization: Bearer <access_token>
```

## Endpoint overview

### Auth

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/api/auth/register` | — | Create an account (returns a token). |
| `POST` | `/api/auth/login` | — | Log in with username **or** email. |
| `GET` | `/api/auth/me` | 🔒 | Current user. |
| `PATCH` | `/api/auth/me` | 🔒 | Update bio / password. |
| `DELETE` | `/api/auth/me` | 🔒 | Delete the account and its content. |

### Articles

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/articles` | — | Paginated list. Filters: `category`, `tag`, `author`, `q`, `published`, `sort`, `page`, `per_page`. |
| `POST` | `/api/articles` | 🔒 | Create an article. |
| `GET` | `/api/articles/{id}` | — | Article detail (drafts: author only). |
| `PUT`/`PATCH` | `/api/articles/{id}` | 🔒 | Update your article. |
| `DELETE` | `/api/articles/{id}` | 🔒 | Delete your article. |

### Categories & tags

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/categories` | — | List categories (`?q=`). |
| `POST` | `/api/categories` | 🔒 | Create a category. |
| `GET` | `/api/categories/{id}` | — | Category detail. |
| `PUT`/`PATCH` | `/api/categories/{id}` | 🔒 | Update a category. |
| `DELETE` | `/api/categories/{id}` | 🔒 | Delete a category (articles are kept). |
| `GET` | `/api/tags` | — | List hashtags, most used first (`?q=`, `?limit=`). |
| `POST` | `/api/tags` | 🔒 | Create a hashtag. |
| `GET` | `/api/tags/{id}` | — | Hashtag detail. |
| `DELETE` | `/api/tags/{id}` | 🔒 | Delete a hashtag. |

### Comments & likes

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/articles/{id}/comments` | — | Paginated comments of an article. |
| `POST` | `/api/articles/{id}/comments` | 🔒 | Comment on an article. |
| `GET` | `/api/comments/{id}` | — | Comment detail. |
| `PUT`/`PATCH` | `/api/comments/{id}` | 🔒 | Edit your comment. |
| `DELETE` | `/api/comments/{id}` | 🔒 | Delete your comment. |
| `GET` | `/api/users/{id}/comments` | — | Comments written by a user. |
| `GET` | `/api/articles/{id}/likes` | — | Who liked an article (+ count). |
| `POST` | `/api/articles/{id}/likes` | 🔒 | Like an article (idempotent). |
| `DELETE` | `/api/articles/{id}/likes` | 🔒 | Remove your like. |

## Response shapes

Paginated collections:

```json
{
  "items": [ { "…": "…" } ],
  "meta": { "page": 1, "per_page": 10, "total": 4, "pages": 1,
            
            "has_next": false, "has_prev": false }
}
```

Errors:

```json
{ "error": { "code": 400, "message": "Validation failed.",
             "details": { "title": ["Shorter than minimum length 3."] } } }
```

## Example requests

```bash
# Register
curl -X POST http://127.0.0.1:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"carol","email":"carol@example.com","password":"secret123"}'

# Create an article (paste the access_token)
curl -X POST http://127.0.0.1:5000/api/articles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Hello world","content":"My first post.",
       "category_id":1,"tags":["flask","hello"]}'

# Public: list articles of the "technology" category tagged "python"
curl "http://127.0.0.1:5000/api/articles?category=technology&tag=python&page=1&per_page=5"

# Like an article
curl -X POST http://127.0.0.1:5000/api/articles/1/likes -H "Authorization: Bearer $TOKEN"
```

## Notes & design choices

- **SQLite** is used by default (`blog.db` at the project root). Override with
  `DATABASE_URL=postgresql://…` — the code is database-agnostic.
- `PRAGMA foreign_keys=ON` is enabled per connection so `ON DELETE CASCADE`
  works as declared in the models.
- Passwords are hashed with Werkzeug's PBKDF2 implementation.
- Article slugs are generated automatically and de-duplicated (`hello-world-2`).
- `flask --app run.py init-db` creates the schema; migrations can be added with
  Flask-Migrate (`flask --app run.py db init && flask --app run.py db migrate`).
