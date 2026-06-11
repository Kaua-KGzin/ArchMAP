FROM python:3.13-slim

LABEL org.opencontainers.image.title="ArchMAP" \
      org.opencontainers.image.description="Static architecture analysis and visualization for software projects." \
      org.opencontainers.image.url="https://github.com/KGzin/ArchMAP" \
      org.opencontainers.image.source="https://github.com/KGzin/ArchMAP" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# Project code is mounted here at runtime
WORKDIR /project

EXPOSE 3000

ENTRYPOINT ["archmap"]

# Default: serve the mounted project in the container
CMD ["serve", ".", "--host", "0.0.0.0", "--port", "3000", "--no-open"]
