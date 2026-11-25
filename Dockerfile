FROM python:3.15-slim

LABEL org.opencontainers.image.title="ArchMAP" \
      org.opencontainers.image.description="Static architecture analysis and visualization for software projects." \
      org.opencontainers.image.url="https://github.com/Kaua-KGzin/ArchMAP" \
      org.opencontainers.image.source="https://github.com/Kaua-KGzin/ArchMAP" \
      org.opencontainers.image.licenses="MIT"

# Without PYTHONUNBUFFERED a long-running `serve` printed nothing to `docker logs`:
# stdout is block-buffered when there is no TTY, so not even the Web UI address showed.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir . \
    && useradd --uid 1000 --create-home --shell /usr/sbin/nologin archmap

# Project code is mounted here at runtime
WORKDIR /project

# Run without root. UID 1000 matches the default user on most Linux hosts, so a
# bind-mounted project stays readable; pass `--user "$(id -u):$(id -g)"` if yours differs.
# Cache writes into the mounted project are best-effort (OSError is ignored).
USER archmap

EXPOSE 3000

ENTRYPOINT ["archmap"]

# Default: serve the mounted project in the container
CMD ["serve", ".", "--host", "0.0.0.0", "--port", "3000", "--no-open"]
