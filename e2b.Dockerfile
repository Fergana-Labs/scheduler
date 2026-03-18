FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/user/scheduler

COPY e2b.pyproject.toml /home/user/scheduler/pyproject.toml
COPY src/scheduler/__init__.py /home/user/scheduler/src/scheduler/__init__.py
COPY src/scheduler/config.py /home/user/scheduler/src/scheduler/config.py
COPY src/scheduler/sandbox /home/user/scheduler/src/scheduler/sandbox
COPY src/scheduler/onboarding /home/user/scheduler/src/scheduler/onboarding
COPY src/scheduler/guides /home/user/scheduler/src/scheduler/guides
COPY src/scheduler/drafts /home/user/scheduler/src/scheduler/drafts

RUN python3 -m pip install --break-system-packages -e .
