# --- Build-Stage: Wheel bauen (Audit SCALE-004: Multi-Stage) ------------------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir build

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN python -m build --wheel --outdir /dist


# --- Runtime-Stage: schlankes Image, non-root (Audit SEC-007) -----------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Non-root-User mit hoher UID (Audit SEC-007)
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app

COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

# Cloud-Transport. MCP_HOST=0.0.0.0 NUR im Container (Audit SEC-016) —
# der Code-Default bleibt 127.0.0.1.
ENV MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

USER app

# Liveness-Check gegen den /health-Endpoint (Audit SCALE-004)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["python", "-m", "swiss_environment_mcp.server"]
