FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала зависимости: этот слой кэшируется, пока requirements.txt не менялся
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Статика для DRF browsable API (SECRET_KEY здесь только заглушка для сборки)
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput

# Запуск не от root
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Миграции (включая сид номеров) применяются при старте, затем запускается gunicorn
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
