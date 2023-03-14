#!/bin/bash
set -euo pipefail

base="$(dirname "$0")"

pip uninstall -y -r "$base/../python/requirements.txt"
pip install -r "$base/../python/requirements-direct.txt"

pip install pipdeptree
grep -e "^#" -e ";" "$base/../python/requirements-direct.txt" > "$base/../python/requirements.txt"
pipdeptree --packages=$(grep -v "^#" "$base/../python/requirements-direct.txt" | sed -e "s/;.*//" -e "s/=.*//g" | paste -s -d ,) --freeze >> "$base/../python/requirements.txt"

git diff "$base/../python/requirements.txt"

