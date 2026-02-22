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

        with open(project_root / 'docker' / 'action.yml', encoding='utf-8') as r:
            docker_action = yaml.safe_load(r)

        default_docker_tag = docker_action.get('inputs', {}).get('docker_tag', {}).get('default')
        self.assertEqual(default_docker_tag, version, 'version in docker/action.yml must match __version__ in python/publish/__init__.py')


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
        # these are documented in the action.yml files but not forwarded to docker
        obsolete_inputs = ['github_token_actor']
        expected = {key.upper(): f'${{{{ inputs.{key} }}}}'
                    for key in list(composite_action.get('inputs', {}).keys() - obsolete_inputs) + extra_inputs}

        steps = composite_action.get('runs', {}).get('steps', [])
        steps = [step for step in steps if step.get('name') == 'Publish Test Results']
        self.assertTrue(len(steps) > 0)
        for step in steps:
            self.assertIn('env', step, step.get('name'))
            inputs = {key.upper(): value for key, value in step.get('env', {}).items()}
            self.assertEqual(expected, inputs)

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

    def test_docker_action(self):
        with open(project_root / 'action.yml', encoding='utf-8') as r:
            base_action = yaml.safe_load(r)
        expected_inputs = list(base_action.get('inputs', {}).keys() - ['github_token_actor']) + ['log_level', 'root_log_level']

        with open(project_root / 'docker' / 'action.yml', encoding='utf-8') as r:
            docker_action = yaml.safe_load(r)

        docker_action_steps = docker_action.get('runs', {}).get('steps', [])
        self.assertEqual(len(docker_action_steps), 1)
        docker_action_step = docker_action_steps[0]

        docker_image_env = docker_action_step.get('env', {})
        self.assertTrue(docker_image_env)
        envs = [var[6:].lower() for var in docker_image_env.keys()]
        self.assertEqual(sorted(expected_inputs), sorted(envs))
        expected_env_vals = ["inputs." + env for env in envs]
        actual_env_vals = [val[3:][:-2].strip() for val in docker_image_env.values() if val.startswith('${{') and val.endswith('}}')]
        self.assertEqual(expected_env_vals, actual_env_vals)

        docker_image_run = docker_action_step.get('run', {})
        self.assertTrue(docker_image_run)
        vars = [var[7:-1].lower() if var.startswith('"') and var.endswith('"') else var[6:].lower()
                for line in docker_image_run.split('\n')
                for part in line.split(' ')
                for var in [part.strip()]
                if var.startswith('INPUT_') or var.startswith('"INPUT_')]
        self.assertEqual(sorted(expected_inputs), sorted(vars))

    def test_action_types(self):
        self.do_test_action_types('.')

    def test_composite_action_types(self):
        self.do_test_action_types('composite')

    def test_docker_action_types(self):
        self.do_test_action_types('docker', extra_inputs={
            'docker_platform': {'type': 'string'},
            'docker_registry': {'type': 'string'},
            'docker_image': {'type': 'string'},
            'docker_tag': {'type': 'string'},
        })

    def test_linux_action_types(self):
        self.do_test_action_types('linux')

    def test_macos_action_types(self):
        self.do_test_action_types('macos')

    def test_windows_action_types(self):
        self.do_test_action_types('windows')

    def test_windows_bash_action_types(self):
        self.do_test_action_types('windows/bash')

    def do_test_action_types(self, subaction: str, extra_inputs: dict = None):
        with open(project_root / 'action-types.yml', encoding='utf-8') as r:
            root_action_types = yaml.safe_load(r)
        if extra_inputs:
            root_action_types.get('inputs', {}).update(extra_inputs)

        with open(project_root / f'{subaction}/action.yml', encoding='utf-8') as r:
            action = yaml.safe_load(r)

        with open(project_root / f'{subaction}/action-types.yml', encoding='utf-8') as r:
            action_types = yaml.safe_load(r)

        self.assertEqual(action_types.get('inputs', {}).keys(), action.get('inputs', {}).keys())
        self.assertEqual(action_types.get('outputs', {}).keys(), action.get('outputs', {}).keys())
        self.assertEqual(action_types, root_action_types)

    def test_proxy_action(self):
        # TODO
        # run RUNNER_OS=Linux|Windows|macOS GITHUB_ACTION_PATH=... composite/proxy.sh
        # and compare with python/test/files/proxy.yml
        pass
