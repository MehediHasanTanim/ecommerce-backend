# E-Commerce Backend (Phase 1)

This is a production-grade e-commerce backend built with Django, Django REST Framework, PostgreSQL, Redis, and Celery.

## Prerequisites
- Docker
- Docker Compose

## Quick Start

1. Clone the repository.
2. Build and run the containers:
   ```bash
   docker-compose up --build
   ```
3. Run migrations (in a new terminal):
   ```bash
   docker-compose exec web python manage.py migrate
   ```
4. Create a superuser:
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

## API Documentation
- **Swagger UI**: [http://localhost:8000/api/docs/swagger/](http://localhost:8000/api/docs/swagger/)
- **ReDoc**: [http://localhost:8000/api/docs/redoc/](http://localhost:8000/api/docs/redoc/)
- **Schema**: [http://localhost:8000/api/schema/](http://localhost:8000/api/schema/)

## Testing
Run the tests with coverage:
```bash
docker-compose exec web pytest --cov=apps --cov-report=term-missing
```

## Structure
- `config/`: Main project configuration (settings, urls, wsgi, asgi)
- `apps/`: Django applications (users, catalog, orders, etc.)
- `requirements/`: Project dependencies
- `docker/`: Dockerfiles and related configuration
