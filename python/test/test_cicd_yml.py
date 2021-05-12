import unittest

import yaml
from yaml import Loader


class TestActionYml(unittest.TestCase):

    def test_cicd_workflow(self):
        with open('../../action.yml', encoding='utf-8') as r:
            action = yaml.load(r, Loader=Loader)

        with open('../../.github/workflows/ci-cd.yml', encoding='utf-8') as r:
            cicd = yaml.load(r, Loader=Loader)

        docker_image_steps = cicd.get('jobs', []).get('publish-docker-image', {}).get('steps', [])
        docker_image_step = [step
                             for step in docker_image_steps
                             if step.get('name') == 'Publish Unit Test Results']
        self.assertEqual(1, len(docker_image_step))
        docker_image_run = docker_image_step[0].get('run')
        self.assertTrue(docker_image_run)
        vars = [var[6:].lower()
                for line in docker_image_run.split('\n')
                for part in line.split(' ')
                for var in [part.strip()]
                if var.startswith('INPUT_')]

        self.assertEqual(sorted(action.get('inputs', {}).keys()), sorted(vars))
