# -*- coding: utf-8 -*-
import json
import os

import boto3
import requests


def handler(event, context):
    print('fetching token')

    secret_name = os.environ['SECRET_NAME']
    region_name = "eu-central-1"

    secrets = boto3.client(service_name='secretsmanager', region_name=region_name)
    tokens = secrets.get_secret_value(SecretId=secret_name).get('SecretString')
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
        number = number.replace(',', '')
        if number.endswith('M'):
          number = float(number.rstrip('M'))
          number = number * 1000000
        return int(number)
    
    total = 0
    change = 0
    for tag, url in versions.items():
        response = requests.get(url).text
        lines = iter(response.split('\n'))
        tag_total = None
        tag_change = None
        try:
            while True:
                line = next(lines)
                if 'Total download' in line:
                    tag_total = extract(next(lines))
                if 'Last 30 days' in line:
                    tag_change = extract(next(lines))
        except StopIteration:
            pass

        if tag_total:
            total += tag_total
        if tag_change:
            change += tag_change

        print(f'{tag} total {tag_total} change {tag_change}')

    print('')
    print(f'all total {total} change {change}')
    
    #print('pushing values to s3')
    #s3 = boto3.client('s3')
    #s3.put_object(Body=str(total).encode('utf-8'), Bucket='github.com-enricomi', Key='publish-unit-test-result.pull.total', ACL='public-read')
    #s3.put_object(Body=str(change).encode('utf-8'), Bucket='github.com-enricomi', Key='publish-unit-test-result.pull.month', ACL='public-read')
