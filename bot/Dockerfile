FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Движки-ревьюеры (те же, что в SP1)
RUN npm install -g @alibaba-group/open-code-review \
    && pip install --no-cache-dir "pr-agent==0.36.1"

WORKDIR /app
COPY pyproject.toml ./
COPY review_bot ./review_bot
RUN pip install --no-cache-dir .

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

EXPOSE 8000
CMD ["uvicorn", "review_bot.main:app", "--host", "0.0.0.0", "--port", "8000"]
