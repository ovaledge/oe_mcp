FROM public.ecr.aws/lambda/python:3.12

# Install poetry
RUN pip install poetry --no-cache-dir

# Copy dependency files first for layer caching
COPY pyproject.toml poetry.lock ./

# Dependencies only: do not install the repo as a wheel (readme + packages are not copied yet).
RUN poetry config virtualenvs.create false && \
    poetry install --without dev --no-root --no-interaction --no-ansi

# Copy application code
COPY server/ ./server/
COPY entrypoints/ ./entrypoints/

# Lambda handler
CMD ["entrypoints.lambda_handler.handler"]
