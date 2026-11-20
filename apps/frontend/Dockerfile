# Build from the repository root:
#   docker build -f apps/frontend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY apps/frontend/requirements.txt /app/apps/frontend/requirements.txt
RUN pip install -r /app/apps/frontend/requirements.txt

COPY apps/frontend /app/apps/frontend

RUN useradd --create-home --uid 10002 dashboard && chown -R dashboard:dashboard /app
USER dashboard

WORKDIR /app/apps/frontend
EXPOSE 8501

# AGRISHIELD_API_URL must be reachable from *this container*, not the browser.
ENV AGRISHIELD_API_URL=http://127.0.0.1:8000/api/v1
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4).status == 200 else 1)"

# Streamlit has no env-var syntax for list options, so the deployment-supplied
# allowlists are expanded here, at start time.
CMD ["sh", "-c", "exec streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true ${AGRISHIELD_ALLOWED_HOSTS:+--server.allowedHosts=$AGRISHIELD_ALLOWED_HOSTS} ${AGRISHIELD_ALLOWED_ORIGINS:+--server.corsAllowedOrigins=$AGRISHIELD_ALLOWED_ORIGINS}"]
