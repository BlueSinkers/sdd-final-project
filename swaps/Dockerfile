FROM python:3.12-slim

# The commit this image is built from; CI passes --build-arg GIT_SHA=<sha> and
# /health reports it as "version". Not a secret.
ARG GIT_SHA=dev
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GIT_SHA=${GIT_SHA}
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only what the service needs at runtime: no tests, no .env, never COPY . .
COPY app/ ./app/
COPY migrations/ ./migrations/

RUN useradd --system --uid 10001 appuser
USER appuser

EXPOSE 8000
# --no-access-log: the app writes its own single line per request (see app/main.py).
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
