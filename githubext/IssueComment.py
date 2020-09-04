import github
from github import GithubObject
from github.IssueComment import IssueComment


@property
def node_id(self):
    """
    :type: string
    """
    self._completeIfNotSet(self._node_id)
    return self._node_id.value


orig_initAttributes = IssueComment._initAttributes
orig_useAttributes = IssueComment._useAttributes


def _initAttributes(self):
    self._node_id = github.GithubObject.NotSet
    orig_initAttributes(self)


def _useAttributes(self, attributes):
    if "node_id" in attributes:  # pragma no branch
        self._node_id = self._makeStringAttribute(attributes["node_id"])
    orig_useAttributes(self, attributes)


github.IssueComment.IssueComment.node_id = node_id
github.IssueComment.IssueComment._initAttributes = _initAttributes
github.IssueComment.IssueComment._useAttributes = _useAttributes
