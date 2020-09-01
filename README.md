# GitHub Action to Publish Unit Test Results

This [GitHub Action](https://github.com/actions) analyses Unit Test result files and
publishes the results on GitHub. It supports the JUnit XML file format.

You can add this action to your GitHub workflow and configure it as follows:

```yaml
- name: Publish Unit Test Results
  uses: EnricoMi/publish-unit-test-result-action@master
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    files: test-results/**/*.xml
    log_level: DEBUG
```

**Note:** The action can only be used on `push` events.

The `log_level` variable is optional. The default value is `INFO`. The Python logging module defines the [available log levels](https://docs.python.org/3/library/logging.html#logging-levels).

Test results can be found in GitHub at multiple positions:
