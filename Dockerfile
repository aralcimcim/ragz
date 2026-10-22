FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 app && chown app:app /app
COPY --chown=app:app build_index.py retrieval.py trials.py ./
USER app
ARG INDEX_LIMIT=10
RUN python build_index.py --topic All --limit "$INDEX_LIMIT"
COPY --chown=app:app app.py rag.py ui.py styles.css workspace.py ./
COPY --chown=app:app concept_canvas concept_canvas
COPY --chown=app:app fonts fonts
COPY --chown=app:app .streamlit .streamlit
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
