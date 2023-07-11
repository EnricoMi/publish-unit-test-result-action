#!/bin/bash
set -euo pipefail

base="$(dirname "$0")"

pip install --upgrade --force pip==22.0.0
pip install --upgrade --upgrade-strategy eager -r "$base/../python/requirements-direct.txt"

pip install pipdeptree
pipdeptree --packages="$(sed -e "s/;.*//" -e "s/=.*//g" "$base/../python/requirements-direct.txt" | paste -s -d ,)" --freeze > "$base/../python/requirements.txt"

git diff "$base/../python/requirements.txt"

