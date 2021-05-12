import unittest

import yaml
from yaml import Loader


class TestActionYml(unittest.TestCase):

    def test_composite_action(self):
        with open('../../action.yml', encoding='utf-8') as r:
            dockerfile_action = yaml.load(r, Loader=Loader)

        with open('../../composite/action.yml', encoding='utf-8') as r:
            composite_action = yaml.load(r, Loader=Loader)

        self.assertIn('runs', dockerfile_action)
        self.assertIn('runs', composite_action)
        dockerfile_action_wo_runs = {k:v for k,v in dockerfile_action.items() if k != 'runs'}
        composite_action_wo_runs = {k:v for k,v in composite_action.items() if k != 'runs'}
        self.assertEqual(dockerfile_action_wo_runs, composite_action_wo_runs)
        self.assertIn(('using', 'composite'), composite_action.get('runs', {}).items())

    def test_composite_inputs(self):
        with open('../../composite/action.yml', encoding='utf-8') as r:
            action = yaml.load(r, Loader=Loader)

        # these are not documented in the action.yml files but still needs to be forwarded
        extra_inputs = ['root_log_level', 'log_level']
        expected = {key.upper(): f'${{{{ inputs.{key} }}}}' for key in list(action.get('inputs', {}).keys()) + extra_inputs}

        steps = action.get('runs', {}).get('steps', [])
        step = next((step for step in steps if step.get('name') == 'Publish Unit Test Results'), {})
        inputs = {key.upper(): value for key, value in step.get('env', {}).items()}
        self.assertEqual(expected, inputs)
