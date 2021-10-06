import logging
import re
from dataclasses import dataclass
from typing import List, Any, Optional, Tuple, Mapping

from github import Github, GithubException
from github.CheckRun import CheckRun
from github.CheckRunAnnotation import CheckRunAnnotation
from github.PullRequest import PullRequest

from publish import hide_comments_mode_orphaned, hide_comments_mode_all_but_latest, \
    comment_mode_off, comment_mode_create, comment_mode_update, digest_prefix, \
    get_stats_from_digest, digest_header, get_short_summary, get_long_summary_md, \
    get_long_summary_with_digest_md, get_error_annotations, get_case_annotations, \
    get_all_tests_list_annotation, get_skipped_tests_list_annotation, get_all_tests_list, \
    get_skipped_tests_list, all_tests_list, skipped_tests_list, pull_request_build_mode_merge, \
    Annotation, SomeTestChanges
from publish import logger
from publish.github_action import GithubAction
from publish.unittestresults import UnitTestCaseResults, UnitTestRunResults, get_stats_delta


@dataclass(frozen=True)
class Settings:
    token: str
    api_url: str
    graphql_url: str
    api_retries: int
    event: dict
    event_file: Optional[str]
    event_name: str
    repo: str
    commit: str
    fail_on_errors: bool
    fail_on_failures: bool
    files_glob: str
    check_name: str
    comment_title: str
    comment_mode: str
    compare_earlier: bool
    pull_request_build: str
    test_changes_limit: int
    hide_comment_mode: str
    report_individual_runs: bool
    dedup_classes_by_file_name: bool
    check_run_annotation: List[str]
    seconds_between_github_reads: float
    seconds_between_github_writes: float


class Publisher:

    def __init__(self, settings: Settings, gh: Github, gha: GithubAction):
        self._settings = settings
        self._gh = gh
        self._gha = gha
        self._repo = gh.get_repo(self._settings.repo)
        self._req = gh._Github__requester

    def publish(self,
                stats: UnitTestRunResults,
                cases: UnitTestCaseResults,
                conclusion: str):
        logger.info(f'publishing {conclusion} results for commit {self._settings.commit}')
        check_run = self.publish_check(stats, cases, conclusion)

        if self._settings.comment_mode != comment_mode_off:
            pull = self.get_pull(self._settings.commit)
            if pull is not None:
                self.publish_comment(self._settings.comment_title, stats, pull, check_run, cases)
                if self._settings.hide_comment_mode == hide_comments_mode_orphaned:
                    self.hide_orphaned_commit_comments(pull)
                elif self._settings.hide_comment_mode == hide_comments_mode_all_but_latest:
                    self.hide_all_but_latest_comments(pull)
                else:
                    logger.info('hide_comments disabled, not hiding any comments')
            else:
                logger.info(f'there is no pull request for commit {self._settings.commit}')
        else:
            logger.info('comment_on_pr disabled, not commenting on any pull requests')

    def get_pull(self, commit: str) -> Optional[PullRequest]:
        issues = self._gh.search_issues(f'type:pr repo:"{self._settings.repo}" {commit}')
        # totalCount calls the GitHub API, so better not do this if we are not logging the result anyway
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'found {issues.totalCount} pull requests in repo {self._settings.repo} for commit {commit}')

        if issues.totalCount == 0:
            return None

        for issue in issues:
            pr = issue.as_pull_request()
            logger.debug(pr)
            logger.debug(pr.raw_data)
            logger.debug(f'PR {pr.html_url}: {pr.head.repo.full_name} -> {pr.base.repo.full_name}')

        # we can only publish the comment to PRs that are in the same repository as this action is executed in
        # so pr.base.repo.full_name must be same as GITHUB_REPOSITORY / self._settings.repo
        # we won't have permission otherwise
        pulls = list([pr
                      for issue in issues
                      for pr in [issue.as_pull_request()]
                      if pr.base.repo.full_name == self._settings.repo])

        if len(pulls) == 0:
            logger.debug(f'found no pull requests in repo {self._settings.repo} for commit {commit}')
            return None
        if len(pulls) > 1:
            pulls = [pull for pull in pulls if pull.state == 'open']
        if len(pulls) == 0:
            logger.debug(f'found no open pull request in repo {self._settings.repo} for commit {commit}')
            return None
        if len(pulls) > 1:
            self._gha.error(f'Found multiple open pull requests for commit {commit}')
            return None

        pull = pulls[0]
        logger.debug(f'found pull request #{pull.number} for commit {commit}')
        return pull

    def get_stats_from_commit(self, commit_sha: str) -> Optional[UnitTestRunResults]:
        check_run = self.get_check_run(commit_sha)
        return self.get_stats_from_check_run(check_run) if check_run is not None else None

    def get_check_run(self, commit_sha: str) -> Optional[CheckRun]:
        if commit_sha is None or commit_sha == '0000000000000000000000000000000000000000':
            return None

        commit = None
        try:
            commit = self._repo.get_commit(commit_sha)
        except GithubException as e:
            if e.status == 422:
                self._gha.warning(str(e.data))
            else:
                raise e

        if commit is None:
            self._gha.error(f'Could not find commit {commit_sha}')
            return None

        runs = commit.get_check_runs()
        # totalCount calls the GitHub API, so better not do this if we are not logging the result anyway
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'found {runs.totalCount} check runs for commit {commit_sha}')

        return self.get_check_run_from_list(list(runs))

    def get_check_run_from_list(self, runs: List[CheckRun]) -> Optional[CheckRun]:
        # filter for runs with the same name as configured
        runs = [run for run in runs if run.name == self._settings.check_name]
        logger.debug(f'there are {len(runs)} check runs with title {self._settings.check_name}')
        if len(runs) == 0:
            return None
        if len(runs) == 1:
            return runs[0]

        # filter based on summary
        runs = [run for run in runs if run.output.summary and digest_prefix in run.output.summary]
        logger.debug(f'there are {len(runs)} check runs with a test result summary')
        if len(runs) == 0:
            return None
        if len(runs) == 1:
            return runs[0]

        # filter for completed runs
        runs = [run for run in runs if run.status == 'completed']
        logger.debug(f'there are {len(runs)} check runs with completed status')
        if len(runs) == 0:
            return None
        if len(runs) == 1:
            return runs[0]

        # pick run that started latest
        return sorted(runs, key=lambda run: run.started_at, reverse=True)[0]

    @staticmethod
    def get_stats_from_check_run(check_run: CheckRun) -> Optional[UnitTestRunResults]:
        summary = check_run.output.summary
        if summary is None:
            return None
        for line in summary.split('\n'):
            logger.debug(f'summary: {line}')

        pos = summary.index(digest_header) if digest_header in summary else None
        if pos:
            digest = summary[pos + len(digest_header):]
            logger.debug(f'digest: {digest}')
            stats = get_stats_from_digest(digest)
            logger.debug(f'stats: {stats}')
            return stats

    @staticmethod
    def get_test_list_from_annotation(annotation: CheckRunAnnotation) -> Optional[List[str]]:
        if annotation is None or not annotation.raw_details:
            return None
        return annotation.raw_details.split('\n')

    def publish_check(self,
                      stats: UnitTestRunResults,
                      cases: UnitTestCaseResults,
                      conclusion: str) -> CheckRun:
        # get stats from earlier commits
        before_stats = None
        if self._settings.compare_earlier:
            before_commit_sha = self._settings.event.get('before')
            logger.debug(f'comparing against before={before_commit_sha}')
            before_stats = self.get_stats_from_commit(before_commit_sha)
        stats_with_delta = get_stats_delta(stats, before_stats, 'earlier') if before_stats is not None else stats
        logger.debug(f'stats with delta: {stats_with_delta}')

        error_annotations = get_error_annotations(stats.errors)
        case_annotations = get_case_annotations(cases, self._settings.report_individual_runs)
        file_list_annotations = self.get_test_list_annotations(cases)
        all_annotations = error_annotations + case_annotations + file_list_annotations

        # we can send only 50 annotations at once, so we split them into chunks of 50
        check_run = None
        all_annotations = [all_annotations[x:x+50] for x in range(0, len(all_annotations), 50)] or [[]]
        for annotations in all_annotations:
            output = dict(
                title=get_short_summary(stats),
                summary=get_long_summary_with_digest_md(stats_with_delta, stats),
                annotations=[annotation.to_dict() for annotation in annotations]
            )

            logger.info('creating check')
            check_run = self._repo.create_check_run(name=self._settings.check_name,
                                                    head_sha=self._settings.commit,
                                                    status='completed',
                                                    conclusion=conclusion,
                                                    output=output)
            logger.debug(f'created check {check_run}')
        return check_run

    @staticmethod
    def get_test_lists_from_check_run(check_run: Optional[CheckRun]) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        if check_run is None:
            return None, None

        all_tests_title_regexp = re.compile(r'^\d+ test(s)? found( \(tests \d+ to \d+\))?$')
        skipped_tests_title_regexp = re.compile(r'^\d+ skipped test(s)? found( \(tests \d+ to \d+\))?$')

        all_tests_message_regexp = re.compile(
            r'^(There is 1 test, see "Raw output" for the name of the test)|'
            r'(There are \d+ tests, see "Raw output" for the full list of tests)|'
            r'(There are \d+ tests, see "Raw output" for the list of tests \d+ to \d+)\.$')
        skipped_tests_message_regexp = re.compile(
            r'^(There is 1 skipped test, see "Raw output" for the name of the skipped test)|'
            r'(There are \d+ skipped tests, see "Raw output" for the full list of skipped tests)|'
            r'(There are \d+ skipped tests, see "Raw output" for the list of skipped tests \d+ to \d+)\.$')

        annotations = list(check_run.get_annotations())
        all_tests_list = Publisher.get_test_list_from_annotations(annotations, all_tests_title_regexp, all_tests_message_regexp)
        skipped_tests_list = Publisher.get_test_list_from_annotations(annotations, skipped_tests_title_regexp, skipped_tests_message_regexp)

        return all_tests_list or None, skipped_tests_list or None

    @staticmethod
    def get_test_list_from_annotations(annotations: List[CheckRunAnnotation],
                                       title_regexp, message_regexp) -> List[str]:
        test_annotations: List[CheckRunAnnotation] = []

        for annotation in annotations:
            if annotation and annotation.title and annotation.message and annotation.raw_details and \
                    title_regexp.match(annotation.title) and \
                    message_regexp.match(annotation.message):
                test_annotations.append(annotation)

        test_lists = [Publisher.get_test_list_from_annotation(test_annotation)
                      for test_annotation in test_annotations]
        test_list = [test
                     for test_list in test_lists
                     if test_list
                     for test in test_list]
        return test_list

    def get_test_list_annotations(self, cases: UnitTestCaseResults) -> List[Annotation]:
        all_tests = get_all_tests_list_annotation(cases) \
            if all_tests_list in self._settings.check_run_annotation else []
        skipped_tests = get_skipped_tests_list_annotation(cases) \
            if skipped_tests_list in self._settings.check_run_annotation else []
        return [annotation for annotation in skipped_tests + all_tests if annotation]

    def publish_comment(self,
                        title: str,
                        stats: UnitTestRunResults,
                        pull_request: PullRequest,
                        check_run: Optional[CheckRun] = None,
                        cases: Optional[UnitTestCaseResults] = None) -> PullRequest:
        # compare them with earlier stats
        base_check_run = None
        if self._settings.compare_earlier:
            base_commit_sha = self.get_base_commit_sha(pull_request)
            if stats.commit == base_commit_sha:
                # we do not publish a comment when we compare the commit to itself
                # that would overwrite earlier comments without change stats
                return pull_request
            logger.debug(f'comparing against base={base_commit_sha}')
            base_check_run = self.get_check_run(base_commit_sha)
        base_stats = self.get_stats_from_check_run(base_check_run) if base_check_run is not None else None
        stats_with_delta = get_stats_delta(stats, base_stats, 'base') if base_stats is not None else stats
        logger.debug(f'stats with delta: {stats_with_delta}')

        # gather test lists from check run and cases
        before_all_tests, before_skipped_tests = self.get_test_lists_from_check_run(base_check_run)
        all_tests, skipped_tests = get_all_tests_list(cases), get_skipped_tests_list(cases)
        test_changes = SomeTestChanges(before_all_tests, all_tests, before_skipped_tests, skipped_tests)

        details_url = check_run.html_url if check_run else None
        summary = get_long_summary_md(stats_with_delta, details_url, test_changes, self._settings.test_changes_limit)
        body = f'## {title}\n{summary}'

        # reuse existing commend when comment_mode == comment_mode_update
        # if none exists or comment_mode != comment_mode_update, create new comment
        if self._settings.comment_mode != comment_mode_update or not self.reuse_comment(pull_request, body):
            logger.info('creating comment')
            pull_request.create_issue_comment(body)

        return pull_request

    def reuse_comment(self, pull: PullRequest, body: str) -> bool:
        # get comments of this pull request
        comments = self.get_pull_request_comments(pull, order_by_updated=True)

        # get all comments that come from this action and are not hidden
        comments = self.get_action_comments(comments)

        # if there is no such comment, stop here
        if len(comments) == 0:
            return False

        # edit last comment
        comment_id = comments[-1].get("databaseId")
        logger.info(f'editing comment {comment_id}')
        if ':recycle:' not in body:
            body = f'{body}\n:recycle: This comment has been updated with latest results.'

        try:
            pull.get_issue_comment(comment_id).edit(body)
        except Exception as e:
            self._gha.warning(f'Failed to edit existing comment #{comment_id}')
            logger.debug('editing existing comment failed', exc_info=e)

        return True

    def get_base_commit_sha(self, pull_request: PullRequest) -> Optional[str]:
        if self._settings.pull_request_build == pull_request_build_mode_merge:
            if self._settings.event:
                # for pull request events we take the other parent of the merge commit (base)
                if self._settings.event_name == 'pull_request':
                    return self._settings.event.get('pull_request', {}).get('base', {}).get('sha')
                # for workflow run events we should take the same as for pull request events,
                # but we have no way to figure out the actual merge commit and its parents
                # we do not take the base sha from pull_request as it is not immutable
                if self._settings.event_name == 'workflow_run':
                    return None

        try:
            # we always fall back to where the branch merged off base ref
            logger.debug(f'comparing {pull_request.base.ref} with {self._settings.commit}')
            compare = self._repo.compare(pull_request.base.ref, self._settings.commit)
            return compare.merge_base_commit.sha
        except:
            logger.warning(f'could not find best common ancestor '
                           f'between base {pull_request.base.sha} '
                           f'and commit {self._settings.commit}')

        return None

    def get_pull_request_comments(self, pull: PullRequest, order_by_updated: bool) -> List[Mapping[str, Any]]:
        order = ''
        if order_by_updated:
            order = ', orderBy: { direction: ASC, field: UPDATED_AT }'

        query = dict(
            query=r'query ListComments {'
                  r'  repository(owner:"' + self._repo.owner.login + r'", name:"' + self._repo.name + r'") {'
                  r'    pullRequest(number: ' + str(pull.number) + r') {'
                  f'      comments(last: 100{order}) {{'
                  r'        nodes {'
                  r'          id, databaseId, author { login }, body, isMinimized'
                  r'        }'
                  r'      }'
                  r'    }'
                  r'  }'
                  r'}'
        )

        headers, data = self._req.requestJsonAndCheck(
            "POST", self._settings.graphql_url, input=query
        )

        return data \
            .get('data', {}) \
            .get('repository', {}) \
            .get('pullRequest', {}) \
            .get('comments', {}) \
            .get('nodes')

    def hide_comment(self, comment_node_id) -> bool:
        input = dict(
            query=r'mutation MinimizeComment {'
                  r'  minimizeComment(input: { subjectId: "' + comment_node_id + r'", classifier: OUTDATED } ) {'
                  r'    minimizedComment { isMinimized, minimizedReason }'
                  r'  }'
                  r'}'
        )
        headers, data = self._req.requestJsonAndCheck(
            "POST", self._settings.graphql_url, input=input
        )
        return data \
            .get('data', {}) \
            .get('minimizeComment', {}) \
            .get('minimizedComment', {}) \
            .get('isMinimized', {})

    def get_action_comments(self, comments: List[Mapping[str, Any]], is_minimized: Optional[bool] = False):
        return list([comment for comment in comments
                     if comment.get('author', {}).get('login') == 'github-actions'
                     and (is_minimized is None or comment.get('isMinimized') == is_minimized)
                     and comment.get('body', '').startswith(f'## {self._settings.comment_title}\n')
                     and ('\nresults for commit ' in comment.get('body') or '\nResults for commit ' in comment.get('body'))])

    def hide_orphaned_commit_comments(self, pull: PullRequest) -> None:
        # rewriting history of branch removes commits
        # we do not want to show test results for those commits anymore

        # get commits of this pull request
        commit_shas = set([commit.sha for commit in pull.get_commits()])

        # get comments of this pull request
        comments = self.get_pull_request_comments(pull, order_by_updated=False)

        # get all comments that come from this action and are not hidden
        comments = self.get_action_comments(comments)

        # get comment node ids and their commit sha (possibly abbreviated)
        matches = [(comment.get('id'), re.search(r'^[Rr]esults for commit ([0-9a-f]{8,40})\.(?:\s.*)?$', comment.get('body'), re.MULTILINE))
                   for comment in comments]
        comment_commits = [(node_id, match.group(1))
                           for node_id, match in matches
                           if match is not None]

        # get those comment node ids whose commit is not part of this pull request any more
        comment_ids = [(node_id, comment_commit_sha)
                       for (node_id, comment_commit_sha) in comment_commits
                       if not any([sha
                                   for sha in commit_shas
                                   if sha.startswith(comment_commit_sha)])]

        # hide all those comments
        for node_id, comment_commit_sha in comment_ids:
            logger.info(f'hiding unit test result comment for commit {comment_commit_sha}')
            self.hide_comment(node_id)

    def hide_all_but_latest_comments(self, pull: PullRequest) -> None:
        # we want to reduce the number of shown comments to a minimum

        # get comments of this pull request
        comments = self.get_pull_request_comments(pull, order_by_updated=False)

        # get all comments that come from this action and are not hidden
        comments = self.get_action_comments(comments)

        # take all but the last comment
        comment_ids = [comment.get('id') for comment in comments[:-1]]

        # hide all those comments
        for node_id in comment_ids:
            logger.info(f'hiding unit test result comment {node_id}')
            self.hide_comment(node_id)
