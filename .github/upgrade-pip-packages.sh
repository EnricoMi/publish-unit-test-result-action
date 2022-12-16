#!/bin/bash
set -euo pipefail

base="$(dirname "$0")"

pip install --upgrade --force pip==22.0.0
pip install --upgrade --upgrade-strategy eager -r "$base/../python/requirements-direct.txt" -c "$base/../python/constraints.txt"

pip install pipdeptree
grep -e "^#" -e ";" "$base/../python/requirements-direct.txt" > "$base/../python/requirements.txt"
pipdeptree --packages="$(grep -v "^#" "$base/../python/requirements-direct.txt" | sed -e "s/;.*//" -e "s/=.*//g" -e "s/ *@.*//" | paste -s -d ,)" --freeze >> "$base/../python/requirements.txt"

git diff "$base/../python/requirements.txt"

