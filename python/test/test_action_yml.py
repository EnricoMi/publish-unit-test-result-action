import hashlib
import pathlib
import sys
import unittest

import yaml

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

from publish import __version__

project_root = pathlib.Path(__file__).resolve().parent.parent.parent


class TestActionYml(unittest.TestCase):

    def test_action_version(self):
        with open(project_root / 'action.yml', encoding='utf-8') as r:
            dockerfile_action = yaml.safe_load(r)

        image = dockerfile_action.get('runs', {}).get('image', '')
        self.assertTrue(image.startswith('docker://'), image)
        version = image.split(':')[-1]
        self.assertEqual(__version__, version, 'version in action.yml must match __version__ in python/publish/__init__.py')

    def test_composite_action(self):
        self.do_test_composite_action('composite')

    def test_linux_action(self):
        self.do_test_composite_action('linux')

    def test_macos_action(self):
        self.do_test_composite_action('macos')

    def test_windows_action(self):
        self.do_test_composite_action('windows')

    def test_windows_bash_action(self):
        self.do_test_composite_action('windows/bash')

    def do_test_composite_action(self, action: str):
        with open(project_root / 'action.yml', encoding='utf-8') as r:
            dockerfile_action = yaml.safe_load(r)

        with open(project_root / f'{action}/action.yml', encoding='utf-8') as r:
            composite_action = yaml.safe_load(r)

        self.assertIn('runs', dockerfile_action)
        self.assertIn('runs', composite_action)
        dockerfile_action_wo_runs = {k: v for k, v in dockerfile_action.items() if k != 'runs'}
        composite_action_wo_runs = {k: v for k, v in composite_action.items() if k != 'runs'}

        # composite action has outputs.json.value, which does not exist for dockerfile action
        self.assertIn('value', composite_action.get('outputs', {}).get('json', {}))
        del composite_action.get('outputs', {}).get('json', {})['value']

        # compare dockerfile action with composite action
        self.assertEqual(dockerfile_action_wo_runs, composite_action_wo_runs)
        self.assertIn(('using', 'composite'), composite_action.get('runs', {}).items())

        # check inputs forwarded to action
        # these are not documented in the action.yml files but still needs to be forwarded
        extra_inputs = ['files', 'root_log_level', 'log_level']
        expected = {key.upper(): f'${{{{ inputs.{key} }}}}'
                    for key in list(composite_action.get('inputs', {}).keys()) + extra_inputs}

        steps = composite_action.get('runs', {}).get('steps', [])
        steps = [step for step in steps if step.get('name') == 'Publish Test Results']
        self.assertTrue(len(steps) > 0)
        for step in steps:
            self.assertIn('env', step, step.get('name'))
            inputs = {key.upper(): value for key, value in step.get('env', {}).items()}
            self.assertEqual(expected, inputs)

        # the 'composite' composite action is just a proxy to the os-specific actions, so there is no caching
        if action != 'composite':
            # check cache key hash is up-to-date in composite action
            # this md5 is linux-based (on Windows, git uses different newlines, which changes the hash)
            if sys.platform != 'win32':
                with open(project_root / 'python' / 'requirements.txt', mode='rb') as r:
                    expected_hash = hashlib.md5(r.read()).hexdigest()
                cache_hash = next(step.get('with', {}).get('key', '').split('-')[-1]
                                  for step in composite_action.get('runs', {}).get('steps', [])
                                  if step.get('uses', '').startswith('actions/cache/restore@'))
                self.assertEqual(expected_hash, cache_hash, msg='Changing python/requirements.txt requires '
                                                                'to update the MD5 hash in composite/action.yaml')

    def test_proxy_action(self):
        # TODO
        # run RUNNER_OS=Linux|Windows|macOS GITHUB_ACTION_PATH=... composite/proxy.sh
        # and compare with python/test/files/proxy.yml
        pass
