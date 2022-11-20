import json
import os

import boto3
import pprint
import requests

print('fetching token')
secrets = boto3.client('secretsmanager')
tokens = secrets.get_secret_value(SecretId='GithubToken').get('SecretString')
token = json.loads(tokens).get('read package')

print('fetching versions')
headers = {'Authorization': f'token {token}'}
response = requests.get('https://api.github.com/users/EnricoMi/packages/container/publish-unit-test-result-action/versions', headers=headers).json()

versions = {tag: package.get('html_url')
            for package in response
            if package.get('metadata', {}).get('package_type') == 'container'
            for container in [package.get('metadata').get('container', {})]
            for tag in container.get('tags', [])
            if tag.startswith('v') and '.' in tag}
print(f'found {len(versions)} versions')


def extract(line: str) -> int:
  number = line.split('>', 2)[1].split('<', 2)[0]
  return int(number.replace(',', ''))

total = 0
change = 0
for url in versions.values():
  print(f'fetching {url}')
  response = requests.get(url).text
  lines = iter(response.split('\n'))
  try:
    while True:
      line = next(lines)
      if 'Total download' in line:
        total += extract(next(lines))
      if 'Last 30 days' in line:
        change += extract(next(lines))
  except:
    pass

  print

print(f'total={total}  change={change}')

print('pushing values to s3')
s3 = boto3.client('s3')
s3.put_object(Body=str(total).encode('utf-8'), Bucket='github.com-enricomi', Key='publish-unit-test-result.pull.total', ACL='public-read')
s3.put_object(Body=str(change).encode('utf-8'), Bucket='github.com-enricomi', Key='publish-unit-test-result.pull.month', ACL='public-read')

