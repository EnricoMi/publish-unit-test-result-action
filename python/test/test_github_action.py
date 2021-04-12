import io
import os
import unittest
from contextlib import contextmanager

from publish.github_action import GithubAction


@contextmanager
def gh_action_test(test: unittest.TestCase, expected: str) -> GithubAction:
    with io.StringIO() as string:
        yield GithubAction(file=string)
        test.assertEqual(f'{expected}{os.linesep}', string.getvalue())


class TestGithubAction(unittest.TestCase):

    def test_set_output(self):
        with gh_action_test(self, '::set-output name=varname::varval') as gha:
            gha.set_output('varname', 'varval')

    def test_add_mask(self):
        with gh_action_test(self, '::add-mask::the mask') as gha:
            gha.add_mask('the mask')

    def test_stop_commands(self):
        with gh_action_test(self, '::stop-commands::the end token') as gha:
            gha.stop_commands('the end token')

    def test_continue_commands(self):
        with gh_action_test(self, '::the end token::') as gha:
            gha.continue_commands('the end token')

    def test_save_state(self):
        with gh_action_test(self, '::save-state name=state-name::state-value') as gha:
            gha.save_state('state-name', 'state-value')

    def test_group(self):
        with gh_action_test(self, '::group::group title') as gha:
            gha.group('group title')

    def test_group_end(self):
        with gh_action_test(self, '::endgroup::') as gha:
            gha.group_end()

    def test_debug(self):
        with gh_action_test(self, '::debug::the message') as gha:
            gha.debug('the message')

    def test_warning(self):
        with gh_action_test(self, '::warning::the message') as gha:
            gha.warning('the message')
        with gh_action_test(self, '::warning file=the file::the message') as gha:
            gha.warning('the message', file='the file')
        with gh_action_test(self, '::warning line=1::the message') as gha:
            gha.warning('the message', line=1)
        with gh_action_test(self, '::warning col=2::the message') as gha:
            gha.warning('the message', column=2)
        with gh_action_test(self, '::warning file=the file,line=1,col=2::the message') as gha:
            gha.warning('the message', file='the file', line=1, column=2)

    def test_error(self):
        with gh_action_test(self, '::error::the message') as gha:
            gha.error('the message')
        with gh_action_test(self, '::error file=the file::the message') as gha:
            gha.error('the message', file='the file')
        with gh_action_test(self, '::error line=1::the message') as gha:
            gha.error('the message', line=1)
        with gh_action_test(self, '::error col=2::the message') as gha:
            gha.error('the message', column=2)
        with gh_action_test(self, '::error file=the file,line=1,col=2::the message') as gha:
            gha.error('the message', file='the file', line=1, column=2)
