from publish import *
import github_action
from unittestresults import UnitTestCaseResults, UnitTestRunResults, \
    get_stats_delta
from github_action import GithubAction


class Settings:
    def __init__(self,
                 token,
                 api_url,
                 event,
                 repo,
                 commit,
                 files_glob,
                 check_name,
                 comment_title,
                 comment_on_pr,
                 hide_comment_mode,
                 report_individual_runs,
                 dedup_classes_by_file_name):
        self.token = token
        self.api_url = api_url
        self.event = event
        self.repo = repo
        self.commit = commit
        self.files_glob = files_glob
        self.check_name = check_name
        self.comment_title = comment_title
        self.comment_on_pr = comment_on_pr
        self.hide_comment_mode = hide_comment_mode
        self.report_individual_runs = report_individual_runs
        self.dedup_classes_by_file_name = dedup_classes_by_file_name


class Publisher:

    _logger = logging.getLogger('publish.publisher')

    from github import Github
    from github.PullRequest import PullRequest
    from githubext.CheckRun import CheckRun
    from githubext.Commit import Commit
    from githubext.IssueComment import IssueComment
    from githubext.Repository import Repository

    # to prevent githubext import to be auto-removed
    if getattr(Repository, 'create_check_run') is None:
        raise RuntimeError('patching github Repository failed')
    if getattr(Commit, 'get_check_runs') is None:
        raise RuntimeError('patching github Commit failed')
    if getattr(IssueComment, 'node_id') is None:
        raise RuntimeError('patching github IssueComment failed')

    def __init__(self, settings: Settings, gh: Github, gha: GithubAction):
        self._settings = settings
        self._gh = gh
        self._gha = gha
        self._repo = gh.get_repo(self._settings.repo)
        self._req = gh._Github__requester

    def publish(self, stats: UnitTestRunResults, cases: UnitTestCaseResults, conclusion: str):
        self._logger.info('publishing {} results for commit {}'.format(conclusion, self._settings.commit))
        check_run = self.publish_check(stats, cases, conclusion)

        if self._settings.comment_on_pr:
            pull = self.get_pull(self._settings.commit)
            if pull is not None:
                self.publish_comment(self._settings.comment_title, stats, pull, check_run)
                if self._settings.hide_comment_mode == hide_comments_mode_orphaned:
                    self.hide_orphaned_commit_comments(pull)
                elif self._settings.hide_comment_mode == hide_comments_mode_all_but_latest:
                    self.hide_all_but_latest_comments(pull)
                else:
                    self._logger.info('hide_comments disabled, not hiding any comments')
            else:
                self._logger.info('there is no pull request for commit {}'.format(self._settings.commit))
        else:
            self._logger.info('comment_on_pr disabled, not commenting on any pull requests')

    def get_pull(self, commit: str) -> Optional[PullRequest]:
        issues = self._gh.search_issues('type:pr {}'.format(commit))
        self._logger.debug('found {} pull requests for commit {}'.format(issues.totalCount, commit))

        if issues.totalCount == 0:
            return None
        self._logger.debug('running in repo {}'.format(self._settings.repo))
        for issue in issues:
            pr = issue.as_pull_request()
            self._logger.debug(pr)
            self._logger.debug(pr.raw_data)
            self._logger.debug('PR {}: {} -> {}'.format(pr.html_url, pr.head.repo.full_name, pr.base.repo.full_name))

        # we can only publish the comment to PRs that are in the same repository as this action is executed in
        # so pr.base.repo.full_name must be same as GITHUB_REPOSITORY
        # we won't have permission otherwise
        pulls = list([pr
                      for issue in issues
                      for pr in [issue.as_pull_request()]
                      if pr.base.repo.full_name == self._settings.repo])

        if len(pulls) == 0:
            self._logger.debug('found no pull requests in repo {} for commit {}'.format(self._settings.repo, commit))
            return None
        if len(pulls) > 1:
            self._gha.error('found multiple pull requests for commit {}'.format(commit))
            return None

        pull = pulls[0]
        self._logger.debug('found pull request #{} for commit {}'.format(pull.number, commit))
        return pull

    def get_stats_from_commit(self, commit_sha: str) -> Optional[UnitTestRunResults]:
        if commit_sha is None or commit_sha == '0000000000000000000000000000000000000000':
            return None

        commit = self._repo.get_commit(commit_sha)
        if commit is None:
            self._gha.error('could not find commit {}'.format(commit_sha))
            return None

        runs = commit.get_check_runs()
        self._logger.debug('found {} check runs for commit {}'.format(runs.totalCount, commit_sha))
        runs = list([run for run in runs if run.name == self._settings.check_name])
        self._logger.debug('found {} check runs for commit {} with title {}'.format(len(runs), commit_sha, self._settings.check_name))
        if len(runs) != 1:
            return None

        summary = runs[0].output.get('summary')
        if summary is None:
            return None
        for line in summary.split('\n'):
            self._logger.debug('summary: {}'.format(line))

        pos = summary.index(digest_prefix) if digest_prefix in summary else None
        if pos:
            digest = summary[pos + len(digest_prefix):]
            self._logger.debug('digest: {}'.format(digest))
            stats = get_stats_from_digest(digest)
            self._logger.debug('stats: {}'.format(stats))
            return stats

    def publish_check(self, stats: UnitTestRunResults, cases: UnitTestCaseResults, conclusion: str) -> CheckRun:
        # get stats from earlier commits
        before_commit_sha = self._settings.event.get('before')
        self._logger.debug('comparing against before={}'.format(before_commit_sha))
        before_stats = self.get_stats_from_commit(before_commit_sha)
        stats_with_delta = get_stats_delta(stats, before_stats, 'ancestor') if before_stats is not None else stats
        self._logger.debug('stats with delta: {}'.format(stats_with_delta))

        check_run = None
        all_annotations = get_annotations(cases, stats.errors, self._settings.report_individual_runs)

        # we can send only 50 annotations at once, so we split them into chunks of 50
        all_annotations = [all_annotations[x:x+50] for x in range(0, len(all_annotations), 50)] or [[]]
        for annotations in all_annotations:
            output = dict(
                title=get_short_summary(stats),
                summary=get_long_summary_with_digest_md(stats_with_delta, stats),
                annotations=[annotation.to_dict() for annotation in annotations]
            )

            self._logger.info('creating check')
            check_run = self._repo.create_check_run(name=self._settings.check_name,
                                                    head_sha=self._settings.commit,
                                                    status='completed',
                                                    conclusion=conclusion,
                                                    output=output)
        return check_run

    def publish_comment(self,
                        title: str,
                        stats: UnitTestRunResults,
                        pull_request: PullRequest,
                        check_run: Optional[CheckRun] = None) -> None:
        # compare them with earlier stats
        base_commit_sha = pull_request.base.sha if pull_request else None
        self._logger.debug('comparing against base={}'.format(base_commit_sha))
        base_stats = self.get_stats_from_commit(base_commit_sha)
        stats_with_delta = get_stats_delta(stats, base_stats, 'base') if base_stats is not None else stats
        self._logger.debug('stats with delta: {}'.format(stats_with_delta))

        self._logger.info('creating comment')
        details_url = check_run.html_url if check_run else None
        pull_request.create_issue_comment(
            '## {}\n{}'.format(title, get_long_summary_md(stats_with_delta, details_url))
        )
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
            "POST", '{}/graphql'.format(self._settings.api_url), input=query
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
            "POST", '{}/graphql'.format(self._settings.api_url), input=input
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
                     and comment.get('body', '').startswith('## {}\n'.format(self._settings.comment_title))
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
            self._logger.info('hiding unit test result comment for commit {}'.format(comment_commit_sha))
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
            self._logger.info('hiding unit test result comment {}'.format(node_id))
            self.hide_comment(node_id)
