FROM python:3.8-alpine

LABEL repository="https://github.com/EnricoMi/publish-unit-test-result-actiona"
LABEL homepage="https://github.com/EnricoMi/publish-unit-test-result-actiona"
LABEL maintainer="Enrico Minacka <github@Enrico.Minack.dev>"

LABEL com.github.actions.name="Publish Test Results abc"
LABEL com.github.actions.description="A GitHub Action to publish test results. abc"
LABEL com.github.actions.icon="check-circlea"
LABEL com.github.actions.color="greena"

RUN apk add --no-cache --upgrade expat libuuid

COPY python/requirements-post-3.7.txt /action/requirements.txt
RUN apk add --no-cache build-base libffi-dev; \
    pip install --upgrade --force --no-cache-dir pip && \
    pip install --upgrade --force --no-cache-dir -r /action/requirements.txt; \
    apk del build-base libffi-dev

COPY python/publish /action/publish
COPY python/publish_test_results.py /action/

ENTRYPOINT ["python", "/action/publish_test_results.py"]
