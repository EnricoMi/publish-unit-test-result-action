import unittest

import github_action as ga


class TestGithubAction(unittest.TestCase):

    def test_set_output(self):
        self.assertEqual('::set-output name=varname::varval', ga.set_output('varname', 'varval'))

    def test_add_mask(self):
        self.assertEqual('::add-mask::the mask', ga.add_mask('the mask'))

    def test_stop_commands(self):
        self.assertEqual('::stop-commands::the end token', ga.stop_commands('the end token'))

    def test_continue_commands(self):
        self.assertEqual('::the end token::', ga.continue_commands('the end token'))

    def test_save_state(self):
        self.assertEqual('::save-state name=state-name::state-value', ga.save_state('state-name', 'state-value'))

    def test_group(self):
        self.assertEqual('::group::group title', ga.group('group title'))

    def test_group_end(self):
        self.assertEqual('::endgroup::', ga.group_end())

    def test_debug(self):
        self.assertEqual('::debug::the message', ga.debug('the message'))

    def test_warning(self):
        self.assertEqual('::warning::the message', ga.warning('the message'))
        self.assertEqual('::warning file=the file::the message', ga.warning('the message', file='the file'))
        self.assertEqual('::warning line=1::the message', ga.warning('the message', line=1))
        self.assertEqual('::warning col=2::the message', ga.warning('the message', column=2))
        self.assertEqual('::warning file=the file,line=1,col=2::the message', ga.warning('the message', file='the file', line=1, column=2))

    def test_error(self):
        self.assertEqual('::error::the message', ga.error('the message'))
        self.assertEqual('::error file=the file::the message', ga.error('the message', file='the file'))
        self.assertEqual('::error line=1::the message', ga.error('the message', line=1))
        self.assertEqual('::error col=2::the message', ga.error('the message', column=2))
        self.assertEqual('::error file=the file,line=1,col=2::the message', ga.error('the message', file='the file', line=1, column=2))
