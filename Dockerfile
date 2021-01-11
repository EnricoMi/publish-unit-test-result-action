FROM python:3.6-alpine

LABEL repository="https://github.com/EnricoMi/publish-unit-test-result-action"
LABEL homepage="https://github.com/EnricoMi/publish-unit-test-result-action"
LABEL maintainer="Enrico Minack <github@Enrico.Minack.dev>"

LABEL com.github.actions.name="Publish Unit Test Results"
LABEL com.github.actions.description="A GitHub Action to publish unit test results."
LABEL com.github.actions.icon="check-circle"
LABEL com.github.actions.color="green"

COPY requirements.txt /action/
RUN pip install --upgrade --force --no-cache-dir pip && pip install --upgrade --force --no-cache-dir -r /action/requirements.txt

COPY github_action /action/github_action
COPY junit /action/junit
COPY publish /action/publish
COPY unittestresults /action/unittestresults
COPY publish_unit_test_results.py /action/

ENTRYPOINT ["python", "/action/publish_unit_test_results.py"]
