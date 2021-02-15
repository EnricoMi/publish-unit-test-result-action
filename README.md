# GitHub Action to Publish Unit Test Results

This [GitHub Action](https://github.com/actions) analyses Unit Test result files and
publishes the results on GitHub. It supports the JUnit XML file format.

Unit test results are published in the GitHub Actions section of the respective commit:

![...](github-checks-comment.png)

***Note:** This action does not fail if unit tests failed. The action that executed the unit tests should
fail on test failure.*

Each failing test will produce an annotation with failure details:
![...](github-checks-annotation.png)

***Note:** Only the first failure of a test is shown. If you want to see all failures, set `report_individual_runs: "true"`.*

A comment is posted on the pull request of that commit, if one exists.
In presence of failures or errors, the comment links to the respective check page with failure details:

![...](github-pull-request-comment.png)

The checks section of the pull request also lists a short summary (here `1 fail, 1 skipped, 17 pass in 12s`),
and a link to the GitHub Actions section (here `Details`):

![...](github-pull-request-checks.png)

The result distinguishes between tests and runs. In some situations, tests run multiple times,
e.g. in different environments. Displaying the number of runs allows spotting unexpected
changes in the number of runs as well.

The change statistics (e.g. 5 tests ±0) might sometimes hide test removal.
Those are highlighted in pull request comments to easily spot unintended test removal:

![...](github-pull-request-comment-with-test-changes.png)

***Note:** This requires `check_run_annotations` to be set to `all tests, skipped tests`.*

The symbols have the following meaning:

|Symbol|Meaning|
|:----:|-------|
|<img src="https://github.githubassets.com/images/icons/emoji/unicode/2714.png" height="20"/>|A successful test or run|
|<img src="https://github.githubassets.com/images/icons/emoji/unicode/1f4a4.png" height="20"/>|A skipped test or run|
|<img src="https://github.githubassets.com/images/icons/emoji/unicode/274c.png" height="20"/>|A failed test or run|
|<img src="https://github.githubassets.com/images/icons/emoji/unicode/1f525.png" height="20"/>|An erroneous test or run|
|<img src="https://github.githubassets.com/images/icons/emoji/unicode/23f1.png" height="20"/>|The duration of all tests or runs|

## Using this Action

You can add this action to your GitHub workflow as follows:

```yaml
- name: Publish Unit Test Results
  uses: EnricoMi/publish-unit-test-result-action@v1
  if: always()
  with:
    files: test-results/**/*.xml
```

The `if: always()` clause guarantees that this action always runs, even if earlier steps (e.g., the unit test step) in your workflow fail.

### Using pre-build Docker images

You can use a pre-built docker image from [GitHub Container Registry](https://docs.github.com/en/free-pro-team@latest/packages/getting-started-with-github-container-registry/about-github-container-registry) (Beta).
This way, the action is not build for every run of your workflow, and you are guaranteed to get the exact same action build:
```yaml
- name: Publish Unit Test Results
  uses: docker://ghcr.io/enricomi/publish-unit-test-result-action:v1
  if: always()
  with:
    github_token: ${{ github.token }}
    files: test-results/**/*.xml
```

***Note:** GitHub Container Registry is currently in [beta phase](https://docs.github.com/en/free-pro-team@latest/packages/getting-started-with-github-container-registry/about-github-container-registry).*
This action may abandon GitHub Container Registry support when GitHub changes its conditions.

### Configuration

The action publishes results to the commit that it has been triggered on.
Depending on the [workflow event](https://docs.github.com/en/free-pro-team@latest/actions/reference/events-that-trigger-workflows#push)
this can be different kinds of commits.
See [GitHub Workflow documentation](https://docs.github.com/en/free-pro-team@latest/actions/reference/events-that-trigger-workflows)
for which commit the `GITHUB_SHA` environment variable actually refers to.

Pull request related events refer to the merge commit, which is not your pushed commit and is not part of the commit history shown
at GitHub. Therefore, the actual pushed commit SHA is used, provided by the [event payload](https://developer.github.com/webhooks/event-payloads/#pull_request).

If you need the action to use a different commit SHA than those described above,
you can set it via the `commit` option:

```yaml
with:
  commit: ${{ your-commit-sha }}
```

The job name in the GitHub Actions section that provides the test results can be configured via the
`check_name` option. It is optional and defaults to `"Unit Test Results"`, as shown in above screenshot.

Each run of the action creates a new comment on the respective pull request with unit test results.
The title of the comment can be configured via the `comment_title` variable.
It is optional and defaults to the `check_name` option.

In the rare situation that your workflow builds and tests the actual commit, rather than the merge commit
provided by GitHub via `GITHUB_SHA`, you can configure the action via `pull_request_build`.
With `commit`, it assumes that the actual commit is being built,
with `merge` it assumes the merge commit is being built.
The default is `merge`.

The `hide_comments` option allows hiding earlier comments to reduce the volume of comments.
The default is `all but latest`, which hides all earlier comments of the action.
Setting the option to `orphaned commits` will hide comments for orphaned commits only.
These are commits that do no longer belong to the pull request (due to commit history rewrite).
Hiding comments can be disabled all together with value `off`.

To disable comments on pull requests completely, set the option `comment_on_pr` to `false`.
Pull request comments are enabled by default.

Files can be selected via the `files` variable, which is optional and defaults to the current working directory.
It supports wildcards like `*`, `**`, `?` and `[]`. The `**` wildcard matches
[directories recursively](https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob): `./`, `./*/`, `./*/*/`, etc.

If multiple runs exist for a test, only the first failure is reported, unless `report_individual_runs` is `true`.

In the rare situation where a project contains test class duplicates with the same name in different files,
you may want to set `deduplicate_classes_by_file_name` to `true`.

With `check_run_annotations`, the check run provides additional information.
Use comma to set multiple values:

- All found tests are displayed with `all tests`.
- All skipped tests are listed with `skipped tests`.

These additional information are only added to the default branch of your repository, e.g. `main` or `master`.
Use `check_run_annotations_branch` to enable this for multiple branches (comma separated list) or all branches (`"*"`).

Pull request comments highlight removal of tests or tests that the pull request moves into skip state.
Those removed or skipped tests are added as a list, which is limited in length by `test_changes_limit`,
which defaults to `5`. Listing these tests can be disabled entirely by setting this limit to `0`.
This feature requires `check_run_annotations` to contain `all tests` in order to detect test addition
and removal, and `skipped tests` to detect new skipped and un-skipped tests, as well as
`check_run_annotations_branch` to contain your default branch.

See this complete list of configuration options for reference:
```yaml
  with:
    github_token: ${{ secrets.PAT }}
    commit: ${{ your-commit-sha }}
    check_name: Unit Test Results
    comment_title: Unit Test Statistics
    hide_comments: all but latest
    comment_on_pr: true
    pull_request_build: commit
    test_changes_limit: 5
    files: test-results/**/*.xml
    report_individual_runs: true
    deduplicate_classes_by_file_name: false
    check_run_annotations_branch: main, master, branch_one
    check_run_annotations: all tests, skipped tests
```

## Support fork repositories

Getting unit test results of pull requests from fork repositories requires some additional setup.

1. Your CI workflow has to run on `pull_request` events.
2. It has to upload unit test result files.
3. Set up an additional workflow on `workflow_run` events, which starts on completion of the CI workflow,
   downloads the unit test result files and runs this action on them.

The following example defines a simple `CI` workflow and the additional `workflow_run` workflow called `Fork`.

```yaml
name: CI

on: [push, pull_request]

jobs:
  build-and-test:
    name: Build and Test
    runs-on: ubuntu-latest
    # always run on push events, but only run on pull_request events when pull request pulls from fork repository
    # for pull requests within the same repository, the pull event is sufficient
    if: >
      github.event_name == 'push' ||
      github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name != github.repository

    steps:
      - name: Checkout
        uses: actions/checkout@v2

      # run your tests here, produce unit test result files in ./test-results/

      - name: Unit Test Results
        uses: EnricoMi/publish-unit-test-result-action@v1
        # the action is useless on pull_request events
        # (it can not create check runs or pull request comments)
        if: always() && github.event_name != 'pull_request'
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          files: "test-results/*.xml"

      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v2
        with:
          path: test-results/*.xml
```

```yaml
name: Fork

on:
  workflow_run:
    workflows: ["CI"]
    types:
      - completed

jobs:
  unit-test-results:
    name: Unit Test Results from Fork
    runs-on: ubuntu-latest
    if: >
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.conclusion != 'skipped'

    steps:
      - name: Download Artifacts
        uses: actions/github-script@v3.1.0
        with:
          script: |
            var artifacts = await github.actions.listWorkflowRunArtifacts({
               owner: context.repo.owner,
               repo: context.repo.repo,
               run_id: ${{ github.event.workflow_run.id }},
            });
            for (const artifact of artifacts.data.artifacts) {
               var download = await github.actions.downloadArtifact({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  artifact_id: artifact.id,
                  archive_format: 'zip',
               });
               var fs = require('fs');
               fs.writeFileSync(`${{github.workspace}}/artifact-${artifact.id}.zip`, Buffer.from(download.data));
            }
      - name: Extract Artifacts
        run: |
           for file in artifact-*.zip
           do
             if [ -e "$file" ]
             then
               dir="${file/%.zip/}"
               mkdir -p "$dir"
               unzip -d "$dir" "$file"
             fi
           done

      - name: Unit Test Results
        uses: EnricoMi/publish-unit-test-result-action@v1
        with:
          commit: ${{ github.event.workflow_run.head_sha }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          files: "**/*.xml"
```

Note: Running this action on `pull_request_target` events is [dangerous if combined with code checkout and code execution](https://securitylab.github.com/research/github-actions-preventing-pwn-requests).

## Use with matrix strategy

In a scenario where your unit tests run multiple times in different environments (e.g. a matrix strategy),
the action should run only once over all test results. For this, put the action into a separate job
that depends on all your test environments. Those need to upload the test results as artifacts, which
are then all downloaded by your publish job.

You will need to use the `if: success() || failure()` clause when you [support fork repositories](#support-fork-repositories): 

```yaml
name: CI

on: [push]

jobs:
  build-and-test:
    name: Build and Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest

    strategy:
      fail-fast: false
      matrix:
        python-version: [3.6, 3.7, 3.8]

    steps:
      - name: Checkout
        uses: actions/checkout@v2

      - name: Setup Python ${{ matrix.python-version }}
        uses: actions/setup-python@v2
        with:
          python-version: ${{ matrix.python-version }}

      - name: PyTest
        run: python -m pytest test --junit-xml pytest.xml

      - name: Upload Unit Test Results
        if: always()
        uses: actions/upload-artifact@v2
        with:
          name: Unit Test Results (Python ${{ matrix.python-version }})
          path: pytest.xml

  publish-test-results:
    name: "Publish Unit Tests Results"
    needs: build-and-test
    runs-on: ubuntu-latest
    # the build-and-test job might be skipped, we don't need to run this job then
    if: success() || failure()

    steps:
      - name: Download Artifacts
        uses: actions/download-artifact@v2
        with:
          path: artifacts

      - name: Publish Unit Test Results
        uses: EnricoMi/publish-unit-test-result-action@v1
        with:
          check_name: Unit Test Results
          github_token: ${{ secrets.GITHUB_TOKEN }}
          files: pytest.xml
```
