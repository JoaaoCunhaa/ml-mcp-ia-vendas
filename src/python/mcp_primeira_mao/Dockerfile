FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN sed -i 's/\r//' requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MCP_TRANSPORT=sse
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "main.py"]