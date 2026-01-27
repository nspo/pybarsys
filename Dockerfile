# alpine version is not usable due to issues with locales
FROM python:3.10

# system dependencies
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -yq --no-install-recommends \
        locales-all 2>&1 \
        | grep -v "delaying package configuration, since apt-utils is not installed" && \
    rm -rf /var/lib/apt/lists/*

# run everything as non-root user
RUN useradd --create-home --home-dir /home/pybarsys pybarsys
RUN mkdir -p /app/static && chown -R pybarsys:pybarsys /app
WORKDIR /app
USER pybarsys
ENV PATH="/home/pybarsys/.local/bin:${PATH}"

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# python dependencies
COPY requirements.txt .
RUN pip install --user -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["./scripts/run_with_gunicorn.sh"]
