FROM public.ecr.aws/lambda/python:3.12

# Install poetry
RUN pip install poetry --no-cache-dir

# Copy dependency files first for layer caching
COPY pyproject.toml poetry.lock ./

# Install dependencies (no dev, no virtualenv in container)
RUN poetry config virtualenvs.create false && \
    poetry install --without dev --no-interaction --no-ansi

# Copy application code
COPY server/ ./server/
COPY entrypoints/ ./entrypoints/

# Lambda handler
CMD ["entrypoints.lambda_handler.handler"]
