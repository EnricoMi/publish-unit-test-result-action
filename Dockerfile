FROM python:3.12-alpine@sha256:236173eb74001afe2f60862de935b74fcbd00adfca247b2c27051a70a6a39a2d

LABEL repository="https://github.com/EnricoMi/publish-unit-test-result-action"
LABEL homepage="https://github.com/EnricoMi/publish-unit-test-result-action"
LABEL maintainer="Enrico Minack <github@Enrico.Minack.dev>"

LABEL com.github.actions.name="Publish Test Results"
LABEL com.github.actions.description="A GitHub Action to publish test results."
LABEL com.github.actions.icon="check-circle"
LABEL com.github.actions.color="green"

RUN apk add --no-cache --upgrade expat libuuid

COPY python/requirements-post-3.9.txt /action/requirements.txt
RUN apk add --no-cache build-base libffi-dev; \
    pip install --upgrade --force --no-cache-dir pip && \
    pip install --upgrade --force --no-cache-dir -r /action/requirements.txt; \
    apk del build-base libffi-dev

COPY python/publish /action/publish
COPY python/publish_test_results.py /action/

ENTRYPOINT ["python", "/action/publish_test_results.py"]
