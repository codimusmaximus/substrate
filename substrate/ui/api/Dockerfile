FROM python:3.12-slim
WORKDIR /app

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

EXPOSE 8000
CMD ["uvicorn", "substrate.ui.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
