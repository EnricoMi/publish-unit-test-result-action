import time
from datetime import datetime, timedelta

from github import Github
from github.CheckRun import CheckRun
from github.CheckRunAnnotation import CheckRunAnnotation
from github.PullRequest import PullRequest
from github.Repository import Repository

from github_action import GithubAction
from publish import *
from unittestresults import UnitTestCaseResults, UnitTestRunResults, get_stats_delta


logger = logging.getLogger('publish.publisher')


@dataclass(frozen=True)
class Settings:
    token: str
    api_url: str
    event: dict
    event_name: str
    repo: str
    commit: str
    files_glob: Optional[str]
    check_name: str
    comment_title: str
    comment_on_pr: bool
    test_changes_limit: int
    hide_comment_mode: str
    report_individual_runs: bool
    dedup_classes_by_file_name: bool
    check_run_annotation: List[str]
    pull_from_fork_timeout: timedelta
    pull_from_fork_interval: timedelta


class Publisher:

    def __init__(self, settings: Settings, gh: Github, gha: GithubAction):
        self._settings = settings
        self._gh = gh
        self._gha = gha
        self._repo = gh.get_repo(self._settings.repo)
        self._req = gh._Github__requester

    def publish(self, stats: UnitTestRunResults, cases: UnitTestCaseResults, conclusion: str):
        logger.info(f'publishing {conclusion} results for commit {self._settings.commit}')
        check_run = self.publish_check(stats, cases, conclusion)

        if self._settings.comment_on_pr:
            pull = self.get_pull(self._settings.commit)
            if pull is not None:
                self.publish_comment(self._settings.comment_title, stats, pull, check_run, cases)
                self.hide_comments(pull)
            else:
                logger.info(f'there is no pull request for commit {self._settings.commit}')
        else:
            logger.info('comment_on_pr disabled, not commenting on any pull requests')

    def publish_from_check_run(self):
        if self._settings.comment_on_pr:
            pull = self.get_pull(self._settings.commit)
            if pull is not None:
                self.publish_comment_from_check_run(self._settings.comment_title, pull)
                self.hide_comments(pull)
            else:
                logger.info(f'there is no pull request for commit {self._settings.commit}')
        else:
            logger.info('comment_on_pr disabled, not commenting on any pull requests')

    def hide_comments(self, pull: PullRequest):
        if self._settings.hide_comment_mode == hide_comments_mode_orphaned:
            self.hide_orphaned_commit_comments(pull)
        elif self._settings.hide_comment_mode == hide_comments_mode_all_but_latest:
            self.hide_all_but_latest_comments(pull)
        else:
            logger.info('hide_comments disabled, not hiding any comments')

    def get_pull(self, commit: str) -> Optional[PullRequest]:
        issues = self._gh.search_issues(f'type:pr repo:"{self._settings.repo}" {commit}')
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

    def get_check_run(self, commit_sha: str, repo: Optional[Repository] = None) -> Optional[CheckRun]:
        if repo is None:
            repo = self._repo

        if commit_sha is None or commit_sha == '0000000000000000000000000000000000000000':
            return None

        commit = repo.get_commit(commit_sha)
        if commit is None:
            self._gha.error(f'Could not find commit {commit_sha}')
            return None

        runs = commit.get_check_runs()
        logger.debug(f'found {runs.totalCount} check runs for commit {commit_sha}')
        for run in runs:
            logger.debug(f'found check run {run.name}')
        runs = list([run for run in runs if run.name == self._settings.check_name])
        logger.debug(f'found {len(runs)} check runs for commit {commit_sha} with title {self._settings.check_name}')
        if len(runs) != 1:
            return None

        return runs[0]

    @staticmethod
    def get_stats_from_check_run(check_run: CheckRun) -> Optional[UnitTestRunResults]:
        summary = check_run.output.summary
        if summary is None:
            return None
        for line in summary.split('\n'):
            logger.debug(f'summary: {line}')

        pos = summary.index(digest_prefix) if digest_prefix in summary else None
        if pos:
            digest = summary[pos + len(digest_prefix):]
            logger.debug(f'digest: {digest}')
            stats = get_stats_from_digest(digest)
            logger.debug(f'stats: {stats}')
            return stats

    @staticmethod
    def get_test_list_from_annotation(annotation: CheckRunAnnotation) -> Optional[List[str]]:
        if annotation is None or not annotation.raw_details:
            return None
        return annotation.raw_details.split('\n')

    def publish_check(self, stats: UnitTestRunResults, cases: UnitTestCaseResults, conclusion: str) -> CheckRun:
        # get stats from earlier commits
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
        return check_run

    @staticmethod
    def get_test_lists_from_check_run(check_run: Optional[CheckRun]) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        if check_run is None:
            return None, None

        all_tests_annotation: Optional[CheckRunAnnotation] = None
        skipped_tests_annotation: Optional[CheckRunAnnotation] = None

        all_tests_title_regexp = re.compile(r'^\d+ test(s)? found$')
        skipped_tests_title_regexp = re.compile(r'^\d+ skipped test(s)? found$')

        all_tests_message_regexp = re.compile(r'^(There is 1 test, see "Raw output" for the name of the test)|(There are \d+ tests, see "Raw output" for the full list of tests)\.$')
        skipped_tests_message_regexp = re.compile(r'^(There is 1 skipped test, see "Raw output" for the name of the skipped test)|(There are \d+ skipped tests, see "Raw output" for the full list of skipped tests)\.$')

        for annotation in check_run.get_annotations():
            if annotation and annotation.title and annotation.message and annotation.raw_details and \
                    all_tests_title_regexp.match(annotation.title) and \
                    all_tests_message_regexp.match(annotation.message):
                if all_tests_annotation is not None:
                    if annotation:
                        logger.error(f'Found multiple annotation with all tests in check run {check_run.id}: {annotation.raw_details}')
                    return None, None
                all_tests_annotation = annotation

            if annotation and annotation.title and annotation.message and annotation.raw_details and \
                    skipped_tests_title_regexp.match(annotation.title) and \
                    skipped_tests_message_regexp.match(annotation.message):
                if skipped_tests_annotation is not None:
                    if annotation:
                        logger.error(f'Found multiple annotation with skipped tests in check run {check_run.id}: {annotation.raw_details}')
                    return None, None
                skipped_tests_annotation = annotation

        return Publisher.get_test_list_from_annotation(all_tests_annotation), \
               Publisher.get_test_list_from_annotation(skipped_tests_annotation)

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
                        cases: Optional[UnitTestCaseResults] = None):
        # compare them with earlier stats
        base_commit_sha = pull_request.base.sha if pull_request else None
        logger.debug(f'comparing against base={base_commit_sha}')
        base_check_run = self.get_check_run(base_commit_sha)
        base_stats = self.get_stats_from_check_run(base_check_run) if base_check_run is not None else None
        stats_with_delta = get_stats_delta(stats, base_stats, 'base') if base_stats is not None else stats
        logger.debug(f'stats with delta: {stats_with_delta}')

        # gather test lists from check run and cases
        before_all_tests, before_skipped_tests = self.get_test_lists_from_check_run(base_check_run)
        all_tests, skipped_tests = get_all_tests_list(cases), get_skipped_tests_list(cases)
        test_changes = SomeTestChanges(before_all_tests, all_tests, before_skipped_tests, skipped_tests)

        logger.info('creating comment')
        details_url = check_run.html_url if check_run else None
        summary = get_long_summary_md(stats_with_delta, details_url, test_changes, self._settings.test_changes_limit)
        pull_request.create_issue_comment(f'## {title}\n{summary}')

    def publish_comment_from_check_run(self, title: str, pull_request: PullRequest):
        commit_sha = self._settings.commit
        logger.info(f'publishing pull request comment from check run of commit {commit_sha}')

        # get check run and stats for commit
        start = datetime.utcnow()
        while True:
            check_run_base = self.get_check_run(commit_sha, pull_request.base.repo)
            check_run_head = self.get_check_run(commit_sha, pull_request.head.repo)
            if check_run_base is not None or check_run_head is not None:
                break
            if datetime.utcnow() - start > self._settings.pull_from_fork_timeout:
                raise RuntimeError(f'could not find a check run for commit {commit_sha}')
            time.sleep(self._settings.pull_from_fork_interval.total_seconds())

        check_run = check_run_base or check_run_head
        stats = self.get_stats_from_check_run(check_run)
        if stats is None:
            raise RuntimeError(f'could not find stats in check run for commit {commit_sha}')

        # compare them with earlier stats
        base_commit_sha = pull_request.base.sha if pull_request else None
        logger.debug(f'comparing against base={base_commit_sha}')
        base_check_run = self.get_check_run(base_commit_sha)
        base_stats = self.get_stats_from_check_run(base_check_run) if base_check_run is not None else None
        stats_with_delta = get_stats_delta(stats, base_stats, 'base') if base_stats is not None else stats
        logger.debug(f'stats with delta: {stats_with_delta}')

        # gather test lists from check run and cases
        all_tests, skipped_tests = self.get_test_lists_from_check_run(check_run)
        before_all_tests, before_skipped_tests = self.get_test_lists_from_check_run(base_check_run)
        test_changes = SomeTestChanges(before_all_tests, all_tests, before_skipped_tests, skipped_tests)

        logger.info('creating comment')
        details_url = check_run.html_url if check_run else None
        summary = get_long_summary_md(stats_with_delta, details_url, test_changes, self._settings.test_changes_limit)
        pull_request.create_issue_comment(f'## {title}\n{summary}')
        return pull_request

    def get_pull_request_comments(self, pull: PullRequest) -> List[Mapping[str, Any]]:
        query = dict(
            query=r'query ListComments {'
                  r'  repository(owner:"' + self._repo.owner.login + r'", name:"' + self._repo.name + r'") {'
                  r'    pullRequest(number: ' + str(pull.number) + r') {'
                  r'      comments(last: 100) {'
                  r'        nodes {'
                  r'          id, author { login }, body, isMinimized'
                  r'        }'
                  r'      }'
                  r'    }'
                  r'  }'
                  r'}'
        )

        headers, data = self._req.requestJsonAndCheck(
            "POST", f'{self._settings.api_url}/graphql', input=query
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
            "POST", f'{self._settings.api_url}/graphql', input=input
        )
        return data \
            .get('data', {}) \
            .get('minimizeComment', {}) \
            .get('minimizedComment', {}) \
            .get('isMinimized', {})

    def get_action_comments(self, comments: List, is_minimized: Optional[bool] = False):
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
        comments = self.get_pull_request_comments(pull)

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
        comments = self.get_pull_request_comments(pull)

        # get all comments that come from this action and are not hidden
        comments = self.get_action_comments(comments)

        # take all but the last comment
        comment_ids = [comment.get('id') for comment in comments[:-1]]

        # hide all those comments
        for node_id in comment_ids:
            logger.info(f'hiding unit test result comment {node_id}')
            self.hide_comment(node_id)
