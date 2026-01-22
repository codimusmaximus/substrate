FROM python:3.12-slim

WORKDIR /app

# Install git and ssh for vault sync
RUN apt-get update && apt-get install -y git openssh-client && rm -rf /var/lib/apt/lists/*

# Setup SSH for GitHub
RUN mkdir -p /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts && \
    chmod 700 /root/.ssh

# Configure git user for commits
RUN git config --global user.email "substrate@bot.local" && \
    git config --global user.name "Substrate Bot"

# Install absurd SDK from local vendor
COPY libs/absurd-sdk /app/libs/absurd-sdk
RUN pip install /app/libs/absurd-sdk

# Install substrate dependencies
COPY pyproject.toml .
RUN pip install .

# Copy substrate code
COPY substrate /app/substrate

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "substrate.core.worker.main"]
