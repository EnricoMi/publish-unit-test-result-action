import pathlib
import unittest

import yaml

project_root = pathlib.Path(__file__).resolve().parent.parent.parent


class TestActionYml(unittest.TestCase):

    def test_readme_md(self):
        with open(project_root / 'action.yml', encoding='utf-8') as r:
            action = yaml.safe_load(r)

        with open(project_root / 'README.md', encoding='utf-8') as r:
            readme = r.readlines()

        for input, config in action.get('inputs').items():
            with self.subTest(input=input):
                if 'deprecated' not in config.get('description', '').lower():
                    self.assertTrue(
                        any(input in line for line in readme),
                        msg=f'There is no line in README.md that mentions {input}'
                    )
