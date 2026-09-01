# Kittygram: проектная работа по облачным сервисам

> **Проектная работа курса «DevOps-инженер облачных сервисов»**  
> Развёртывание инфраструктуры для веб-приложения Kittygram с использованием Terraform, Docker и CI/CD.

## О проекте

Kittygram — веб-приложение для публикации фотографий кошек и их достижений. Проект демонстрирует полный цикл DevOps: создание инфраструктуры в Yandex Cloud через Terraform, контейнеризацию приложения и автоматический деплой через GitHub Actions.

**Деплой:** http://89.169.128.174:9000

## Архитектура

### Docker-образы

Образы публикуются в Docker Hub с тегом `latest`:

| Образ | Описание | Базовый образ |
| ----- | -------- | ------------- |
| `naraka24e1/kittygram_backend:latest` | Django-приложение | python:3.9-slim |
| `naraka24e1/kittygram_frontend:latest` | React-приложение | node:18 |
| `naraka24e1/kittygram_gateway:latest` | Nginx reverse proxy | nginx:1.22.1 |

### Docker Compose сервисы

| Сервис | Порты | Volumes | Зависимости |
| ------ | ----- | ------- | ----------- |
| postgres | 5432 (internal) | pg_data | — |
| backend | 8000 (internal) | static, media | postgres (healthy) |
| frontend | — | frontend_dist | — |
| gateway | 9000:80 | frontend_dist, static, media | backend, frontend |

### Инфраструктура Yandex Cloud (Terraform)

| Ресурс | Описание |
| ------ | -------- |
| VPC | Используется существующая сеть `default` |
| Subnet | `kittygram-subnet` (192.168.10.0/24) |
| Security Group | SSH (22), HTTP gateway (9000), весь исходящий трафик |
| Compute Instance | Ubuntu 24.04, cloud-init (Docker + Docker Compose) |
| Object Storage | S3-бакет для приложения |
| Terraform State | Хранится в S3-бакете Yandex Object Storage |

## CI/CD Pipeline

### Workflow деплоя (`deploy.yml`)

Запускается при push в ветку `main`:

1. **backend_tests** — flake8 (PEP8) и Django-тесты с PostgreSQL
2. **frontend_tests** — npm test для React-приложения
3. **build_and_push_backend / frontend / gateway** — сборка и публикация образов в Docker Hub
4. **deploy** — копирование файлов на сервер по SSH, migrate, collectstatic, перезапуск контейнеров
5. **notify** — уведомление в Telegram об успешном деплое

### Workflow Terraform (`terraform.yml`)

Запускается вручную через `workflow_dispatch`:

| Действие | Описание |
| -------- | -------- |
| `plan` | Просмотр планируемых изменений инфраструктуры |
| `apply` | Создание или обновление ресурсов в Yandex Cloud |
| `destroy` | Удаление инфраструктуры |

## Уведомления

После успешного деплоя Telegram-бот отправляет сообщение с номером сборки и автором коммита.

## Nginx-маршрутизация

| Location | Назначение |
| -------- | ---------- |
| `/api/` | Proxy на backend:8000 |
| `/admin/` | Django admin |
| `/static/` | Статические файлы Django |
| `/media/` | Загруженные изображения |
| `/` | React-приложение (frontend) |

## API Endpoints

### Аутентификация

| Метод | Endpoint | Описание |
| ----- | -------- | -------- |
| POST | `/api/users/` | Регистрация пользователя |
| POST | `/api/token/login/` | Получение токена |
| POST | `/api/token/logout/` | Выход из системы |
| GET | `/api/users/me/` | Текущий пользователь |

### Котики

| Метод | Endpoint | Описание |
| ----- | -------- | -------- |
| GET | `/api/cats/?page={n}` | Список котиков (пагинация по 10) |
| POST | `/api/cats/` | Добавление котика |
| GET | `/api/cats/{id}/` | Информация о котике |
| PATCH | `/api/cats/{id}/` | Обновление |
| DELETE | `/api/cats/{id}/` | Удаление |

### Достижения

| Метод | Endpoint | Описание |
| ----- | -------- | -------- |
| GET | `/api/achievements/` | Список достижений |
| POST | `/api/achievements/` | Добавление достижения |

## Переменные окружения

Пример в `.env.example`:

```bash
POSTGRES_DB=kittygram
POSTGRES_USER=kittygram_user
POSTGRES_PASSWORD=kittygram_password
DB_HOST=postgres
DB_PORT=5432
SECRET_KEY=your-django-secret-key
DEBUG=False
ALLOWED_HOSTS=your-vm-ip,localhost,127.0.0.1
DOCKER_USERNAME=your-dockerhub-username
```

### GitHub Secrets

**Terraform:**

| Secret | Назначение |
| ------ | ---------- |
| `YC_CLOUD_ID` | ID облака Yandex Cloud |
| `YC_FOLDER_ID` | ID каталога |
| `YC_SERVICE_ACCOUNT_KEY_FILE` | JSON-ключ сервисного аккаунта |
| `ACCESS_KEY` / `SECRET_KEY` | Статические ключи Object Storage |
| `YC_TFSTATE_BUCKET` | Бакет для Terraform state |
| `YC_STORAGE_BUCKET_NAME` | Имя S3-бакета приложения |
| `SSH_PUBLIC_KEY` | Публичный SSH-ключ для cloud-init |

**Деплой:**

| Secret | Назначение |
| ------ | ---------- |
| `REMOTE_HOST` | IP виртуальной машины |
| `REMOTE_USER` | Пользователь SSH (ubuntu) |
| `REMOTE_SSH_KEY` | Приватный SSH-ключ |
| `DOCKER_USERNAME` / `DOCKER_PASSWORD` | Docker Hub |
| `POSTGRES_*`, `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Переменные приложения |
| `TELEGRAM_TOKEN` / `TELEGRAM_TO` | Telegram-уведомления |

## Локальная разработка

```bash
git clone https://github.com/Tengu-cloud/cloud-services-engineer-kittygram-final.git
cd cloud-services-engineer-kittygram-final

cp .env.example .env
# отредактируйте .env

docker compose -f docker-compose.production.yml up -d
```

## Тестирование

Файл `tests.yml` в корне репозитория:

```yaml
repo_owner: Tengu-cloud
kittygram_domain: http://89.169.128.174:9000
dockerhub_username: naraka24e1
```

Локальный запуск автотестов:

```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
pytest
```

## Структура проекта

```
kittygram-final/
├── .env.example
├── README.md
├── .github/
│   └── workflows/
│       ├── terraform.yml
│       └── deploy.yml
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── providers.tf
│   ├── cloud-init.yml
│   └── prepare_sa_key.py
├── backend/
├── frontend/
├── nginx/
├── docker-compose.production.yml
├── kittygram_workflow.yml
├── pytest.ini
├── tests.yml
└── tests/
```

## Порядок развёртывания

1. Создать S3-бакет для Terraform state в Yandex Object Storage
2. Добавить секреты в GitHub Actions
3. Запустить **Terraform: plan → apply**
4. Добавить `REMOTE_HOST`, `ALLOWED_HOSTS`, обновить `tests.yml`
5. Push в `main` — автоматический деплой Kittygram

---

