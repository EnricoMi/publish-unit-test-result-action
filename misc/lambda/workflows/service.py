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
    
    print('searching for workflows')

    headers = {'Authorization': f'token {token}'}
    response = requests.get(f'https://api.github.com/search/code?q=%22publish-unit-test-result-action%22+path%3A.github%2Fworkflows%2F+language%3AYAML&type=Code', headers=headers).json()

    total = response['total_count']
    print(f'found {total} workflows')

    print('pushing values to s3')
    s3 = boto3.client('s3')
    s3.put_object(Body=str(total).encode('utf-8'), Bucket='github.com-enricomi', Key='publish-unit-test-result.workflows', ACL='public-read')

