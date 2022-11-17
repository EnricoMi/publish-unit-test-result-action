# -*- coding: utf-8 -*-
from functools import reduce

import boto3
from bs4 import BeautifulSoup
import requests


def handler(event, context):
  print('fetching package page')

  html = requests.get('https://github.com/EnricoMi/publish-unit-test-result-action/pkgs/container/publish-unit-test-result-action').text

  soup = BeautifulSoup(html, 'html.parser')
  downloads = [span.find_next('h3').attrs.get('title')
               for span in soup.find_all('span')
               if span.text == 'Total downloads']
  total = downloads[0]

  rects = soup.find_all('rect')
  counts = [int(rect.attrs.get('data-merge-count')) for rect in rects]
  sum = reduce(lambda a, b: a+b, counts)
  per_day = sum // len(counts)

  print(f'total {total} change {sum} per day {per_day}')

  print('pushing values to s3')
  s3 = boto3.client('s3')
  s3.put_object(Body=str(total).encode('utf-8'), Bucket='github.com-enricomi', Key='publish-unit-test-result.pull.total', ACL='public-read')
  s3.put_object(Body=str(sum).encode('utf-8'), Bucket='github.com-enricomi', Key='publish-unit-test-result.pull.month', ACL='public-read')
  s3.put_object(Body=str(per_day).encode('utf-8'), Bucket='github.com-enricomi', Key='publish-unit-test-result.pull.day', ACL='public-read')
