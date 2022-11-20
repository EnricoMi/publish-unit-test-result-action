import os
import sys

import requests


if len(sys.argv) != 3:
    print('Please provide GitHub API URL and the query string')
    sys.exit(1)

if 'GITHUB_TOKEN' not in os.environ:
    print('Please provide GitHub token via GITHUB_TOKEN environment variable')
    sys.exit(1)

url = sys.argv[1]
query = sys.argv[2]

headers = {'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'}
response = requests.get(f'{url}/search/code?q=%22{query}%22+path%3A.github%2Fworkflows%2F+language%3AYAML&type=Code', headers=headers).json()

total = f'{response["total_count"]:,}'
print(f'found {total} workflows')

if 'GITHUB_OUTPUT' in os.environ:
    with open(os.environ['GITHUB_OUTPUT'], 'wt') as w:
        print(f'total={total}', file=w)
else:
    print(f'::set-output name=total::{total}')
