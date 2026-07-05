FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    AUDIT_DIR=/data/audit

WORKDIR /app

# Dependências primeiro (cache de camadas).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código.
COPY . .

# Usuário não-root — os agentes escrevem apenas em /data.
RUN useradd -m agent && mkdir -p /data/audit && chown -R agent:agent /data
USER agent
VOLUME ["/data"]

# O agente concreto é escolhido via `command` no docker-compose, ex.:
#   python -m agents.banking_benchmark.worker --print
ENTRYPOINT ["python", "-m"]
CMD ["agents.banking_benchmark.worker", "--print"]
