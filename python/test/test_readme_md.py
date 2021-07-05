import unittest

import yaml
from yaml import Loader


class TestActionYml(unittest.TestCase):

    def test_readme_md(self):
        with open('../../action.yml', encoding='utf-8') as r:
            action = yaml.load(r, Loader=Loader)

        with open('../../README.md', encoding='utf-8') as r:
            readme = r.readlines()

        for input, config in action.get('inputs').items():
            with self.subTest(input=input):
                if 'deprecated' not in config.get('description', '').lower():
                    self.assertTrue(
                        any(input in line for line in readme),
                        msg=f'There is no line in README.md that mentions {input}'
                    )
