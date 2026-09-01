FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 10001 cafeteria \
    && useradd --system --uid 10001 --gid cafeteria --home-dir /app --shell /usr/sbin/nologin cafeteria \
    && mkdir -p /app /var/lib/cafeteria/exports \
    && chown -R cafeteria:cafeteria /app /var/lib/cafeteria

WORKDIR /app
COPY reference_scaffold/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=cafeteria:cafeteria reference_scaffold/ /app/
COPY --chown=cafeteria:cafeteria database/ /app/database/
COPY --chown=cafeteria:cafeteria deployment/gunicorn.conf.py /app/gunicorn.conf.py
COPY --chown=cafeteria:cafeteria deployment/healthcheck.py /app/healthcheck.py
COPY --chown=cafeteria:cafeteria deployment/entrypoint.sh /entrypoint.sh
RUN chmod 0555 /entrypoint.sh /app/manage.py /app/healthcheck.py

USER cafeteria
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--config", "/app/gunicorn.conf.py", "wsgi:app"]
