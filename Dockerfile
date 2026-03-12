FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

ENV MCP_TRANSPORT=streamable_http
ENV PORT=8000

EXPOSE 8000

CMD ["python", "-m", "swiss_environment_mcp.server"]
