from functools import reduce
import os
import sys

from bs4 import BeautifulSoup
import requests


if len(sys.argv) != 4:
    print('Please provide GitHub URL, the user/repo name, and the package name as command line arguments')
    sys.exit(1)

url = sys.argv[1]
repo = sys.argv[2]
pkg = sys.argv[3]

url = f'{url}/{repo}/pkgs/container/{pkg}'
html = requests.get(url).text

soup = BeautifulSoup(html, 'html.parser')
downloads = [span.find_next('h3').attrs.get('title')
             for span in soup.find_all('span')
             if span.text == 'Total downloads']
total = downloads[0]

rects = soup.find_all('rect')
counts = [int(rect.attrs.get('data-merge-count')) for rect in rects]
sum = reduce(lambda a, b: a+b, counts)
per_day = sum // len(counts)


def humanize(n):
    suffix = ''
    if n > 1000:
        suffix = 'k'
        n = n / 1000
    if n > 1000:
        suffix = 'M'
        n = n / 1000
    if n > 1000:
        suffix = 'B'
        n = n / 1000
    if n > 100:
        return f'{n:.0f}{suffix}'
    else:
        return f'{n:.1f}{suffix}'


total = humanize(int(total))
per_day = humanize(int(per_day))

print(f'total={total}')
print(f'per_day={per_day}')

if 'GITHUB_OUTPUT' in os.environ:
    print(f'output file is {os.environ["GITHUB_OUTPUT"]}')
    with open(os.environ['GITHUB_OUTPUT'], 'at') as w:
        print(f'total={total}', file=w)
        print(f'per_day={per_day}', file=w)
else:
    print(f'::set-output name=total::{total}')
    print(f'::set-output name=per_day::{per_day}')
