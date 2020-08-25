import logging
import os
import pathlib
from typing import List, Dict, Any
import re

from junitparser import *


def parse_junit_xml_files(files: List[str]) -> Dict[Any, Any]:
    junits = [JUnitXml.fromfile(file) for file in files]

    suites = sum([len(junit) for junit in junits])
    suite_tests = sum([suite.tests for junit in junits for suite in junit])
    suite_skipped = sum([suite.skipped for junit in junits for suite in junit])
    suite_failures = sum([suite.failures for junit in junits for suite in junit])
    suite_errors = sum([suite.errors for junit in junits for suite in junit])
    suite_time = sum([suite.time for junit in junits for suite in junit])

    cases = len([case for junit in junits for suite in junit for case in suite])
    cases_skipped = len([case for junit in junits for suite in junit for case in suite if isinstance(case.result, Skipped)])
    cases_failures = len([case for junit in junits for suite in junit for case in suite if isinstance(case.result, Failure)])
    cases_errors = len([case for junit in junits for suite in junit for case in suite if isinstance(case.result, Error)])
    cases_time = sum([case.time for junit in junits for suite in junit for case in suite])

    return dict(
        files=len(files),

        suites=suites,
        suite_tests=suite_tests,
        suite_skipped=suite_skipped,
        suite_failures=suite_failures,
        suite_errors=suite_errors,
        suite_time=suite_time,

        cases=cases,
        cases_skipped=cases_skipped,
        cases_failures=cases_failures,
        cases_errors=cases_errors,
        cases_time=cases_time
    )


def publish(token: str, repo_name: str, repo_owner: str, commit_sha: str, ref: str, stats: Dict[Any, Any]):
    from github import Github, PullRequest

    gh = Github(token)
    repo = gh.get_user(repo_owner).get_repo(repo_name)
    head = re.sub('.*/', '', ref)

    def publish_check() -> None:
        from githubext import Repository

        summary = '{tests} tests, {skipped} skipped, {failed} failed, {errors} errors'.format(
            tests=stats['suite_tests'],
            skipped=stats['suite_skipped'],
            failed=stats['suite_failures'],
            errors=stats['suite_errors']
        )
        text = ('Unit Test Results ({files} files, {suites} suites, {seconds} seconds):\n'
                '\n'
                '| State | Test Cases |\n'
                '|:-----:|:-----:|\n'
                '| All | {tests} |\n'
                '| Success | {success} |\n'
                '| Skipped | {skipped} |\n'
                '| Failed | {failed} |\n'
                '| Errors | {errors} |').format(
            files=stats['files'],
            suites=stats['suites'],
            tests=stats['suite_tests'],
            success=stats['suite_tests'] - stats['suite_skipped'] - stats['suite_failures'] - stats['suite_errors'],
            skipped=stats['suite_skipped'],
            failed=stats['suite_failures'],
            errors=stats['suite_errors'],
            seconds=stats['suite_time']
        )
        output = dict(
            title='Unit Test Results',
            summary=summary,
            text=text,
        )

        logging.info('creating check')
        check = repo.create_check_run(name='unit-test-result', head_sha=commit_sha, status='completed', conclusion='success', output=output)
        return check.html_url


    def publish_status() -> None:
        commit = repo.get_commit(commit_sha)
        if commit is None:
            raise RuntimeError('Could not find commit {}'.format(commit_sha))

        desc = '{tests} tests, {skipped} skipped, {failed} failed, {errors} errors'.format(
            tests=stats['suite_tests'],
            skipped=stats['suite_skipped'],
            failed=stats['suite_failures'],
            errors=stats['suite_errors']
        )
        logging.info('creating status')
        commit.create_status(state='success', description=desc, context='action/unit-test-results')

    def publish_comment(status) -> None:
        pull = get_pull(head=head, commit=commit_sha)
        if pull is not None:
            logging.info('creating comment')
            pull.create_issue_comment("comment")

    def get_pull(head: str, commit: str) -> PullRequest:
        # get all pulls that have a head that matches 'head'
        pulls = repo.get_pulls(state='all', head=head)
        logging.info('found {} pull requests for head {} (ref={})'.format(pulls.totalCount, head, ref))

        if pulls.totalCount == 0:
            logging.info('Could not find pull request for ref {}'.format(ref))
            return

        # find the pull that exactly references 'head'
        pulls = list([pull for pull in pulls if pull.head.ref == head])
        if len(pulls) > 1:
            for pull in pulls:
                logging.info(pull.head.ref)
            raise RuntimeError('Found multiple pull requests for ref {}'.format(ref))
        pull = pulls[0]

        # double check this pull still contains our commit
        commits = pull.get_commits().get_page(0)
        logging.info('first page of commits:')
        for commit in commits:
            logging.info(commit)

        if len([commit for commit in commits if commit.sha == commit_sha]) == 0:
            logging.info('Could not find commit {} in first page of pull request''s commits'.format(commit_sha))
            return

        return pull

    check = publish_check()
    #publish_status()
    publish_comment(check)


def main(token: str, repo: str, repo_owner: str, commit: str, ref: str, files_glob: str) -> None:
    files = [str(file) for file in pathlib.Path().glob(files_glob)]
    logging.info('{}: {}'.format(files_glob, list(files)))

    if len(files) == 0:
        return

    stats = parse_junit_xml_files(files)
    logging.info(stats)

    publish(token, repo, repo_owner, commit, ref, stats)


def get_repo_name(repo: str) -> str:
    return repo.split('/', 1)[1]


if __name__ == "__main__":
    log_level = os.environ.get('LOG_LEVEL') or 'INFO'
    logger = logging.getLogger()
    logger.level = logging.getLevelName(log_level)

    def get_var(name: str) -> str:
        return os.environ.get('INPUT_{}'.format(name)) or os.environ.get(name)

    token = get_var('GITHUB_TOKEN')
    repo = get_repo_name(get_var('GITHUB_REPOSITORY'))
    repo_owner = get_var('GITHUB_REPOSITORY_OWNER')
    commit = get_var('COMMIT') or os.environ.get('GITHUB_SHA')
    ref = get_var('REF') or os.environ.get('GITHUB_REF')
    files = get_var('FILES')

    def check_var(var: str, name: str, label: str) -> None:
        if var is None:
            raise RuntimeError('{} must be provided via action input or environment variable {}'.format(label, name))

    check_var(token, 'GITHUB_TOKEN', 'GitHub token')
    check_var(repo, 'GITHUB_REPOSITORY', 'GitHub repository')
    check_var(repo_owner, 'GITHUB_REPOSITORY_OWNER', 'GitHub repository owner')
    check_var(commit, 'COMMIT', 'Commit')
    check_var(ref, 'REF', 'Git ref')
    check_var(files, 'FILES', 'Files pattern')

    main(token, repo, repo_owner, commit, ref, files)
