FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir -U pip

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0

EXPOSE 3000

CMD ["python", "-m", "twitter_mcp"]