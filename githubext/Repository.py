#  Copyright 2020 G-Research
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import datetime
from typing import Dict

import github.GithubObject
from github.Repository import Repository

from githubext.CheckRun import CheckRun


def create_check_run(self: Repository,
                     name: str,
                     head_sha: str,
                     details_url: str = github.GithubObject.NotSet,
                     external_id: str = github.GithubObject.NotSet,
                     status: str = github.GithubObject.NotSet,
                     started: datetime.datetime = github.GithubObject.NotSet,
                     conclusion: str = github.GithubObject.NotSet,
                     completed_at: datetime.datetime = github.GithubObject.NotSet,
                     output: Dict = github.GithubObject.NotSet) -> CheckRun:
    """
    :calls: `POST /repos/:owner/:repo/check-runs <http://developer.github.com/v3/checks/runs/>`_
    :param name: str
    :param head_sha: str
    :param details_url: str = None
    :param external_id: str = None
    :param status: str = None
    :param started: datetime.datetime = None
    :param conclusion: str = None
    :param completed_at: datetime.datetime = None
    :param output: Dict = None
    :rtype: :class:`github.CheckRuns.CheckRun`
    """
    assert isinstance(name, str), name
    assert isinstance(head_sha, str), head_sha
    assert details_url is github.GithubObject.NotSet or isinstance(details_url, str), details_url
    assert external_id is github.GithubObject.NotSet or isinstance(external_id, str), external_id
    assert status is github.GithubObject.NotSet or isinstance(status, str), status
    assert started is github.GithubObject.NotSet or isinstance(started, datetime.datetime), started
    assert conclusion is github.GithubObject.NotSet or isinstance(conclusion, str), conclusion
    assert completed_at is github.GithubObject.NotSet or isinstance(completed_at, datetime.datetime), completed_at
    assert output is github.GithubObject.NotSet or isinstance(output, dict), output
    post_parameters = {
        "name": name,
        "head_sha": head_sha
    }
    if details_url is not github.GithubObject.NotSet:
        post_parameters["details_url"] = details_url
    if external_id is not github.GithubObject.NotSet:
        post_parameters["external_id"] = external_id
    if status is not github.GithubObject.NotSet:
        post_parameters["status"] = status
    if started is not github.GithubObject.NotSet:
        post_parameters["started"] = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    if conclusion is not github.GithubObject.NotSet:
        post_parameters["conclusion"] = conclusion
    if completed_at is not github.GithubObject.NotSet:
        post_parameters["completed_at"] = completed_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    if output is not github.GithubObject.NotSet:
        post_parameters["output"] = output
    headers, data = self._requester.requestJsonAndCheck(
        "POST",
        self.url + "/check-runs",
        input=post_parameters,
        headers={'Accept': 'application/vnd.github.antiope-preview+json'},
    )
    return CheckRun(self._requester, headers, data, completed=True)


Repository.create_check_run = create_check_run
