FROM python:3.12-slim

WORKDIR /app

COPY backend/pyproject.toml .
RUN python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    deps = tomllib.load(f)['project']['dependencies']
with open('deps.txt', 'w') as f:
    f.write('\n'.join(deps))
" && pip install --no-cache-dir -r deps.txt

COPY backend/ .

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
