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
        with open(project_root / 'action.yml', encoding='utf-8') as r:
            dockerfile_action = yaml.safe_load(r)

        with open(project_root / 'composite/action.yml', encoding='utf-8') as r:
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

    def test_composite_inputs(self):
        with open(project_root / 'composite/action.yml', encoding='utf-8') as r:
            action = yaml.safe_load(r)

        # these are not documented in the action.yml files but still needs to be forwarded
        extra_inputs = ['files', 'root_log_level', 'log_level']
        expected = {key.upper(): f'${{{{ inputs.{key} }}}}' for key in list(action.get('inputs', {}).keys()) + extra_inputs}

        steps = action.get('runs', {}).get('steps', [])
        step = next((step for step in steps if step.get('name') == 'Publish Test Results'), {})
        inputs = {key.upper(): value for key, value in step.get('env', {}).items()}
        self.assertEqual(expected, inputs)
