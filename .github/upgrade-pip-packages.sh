#!/bin/bash
set -euo pipefail

base="$(dirname "$0")"
python_minor_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

pip install --upgrade --force "pip==24.0.0; python_version <= '3.7'" "pip==25.0.1; python_version == '3.8'" "pip==26.0.1; python_version == '3.9'" "pip==26.1.1; python_version > '3.9'"
pip install --upgrade --upgrade-strategy eager -r "$base/../python/requirements.txt"

pip install pipdeptree
pipdeptree --packages="$(sed -e "s/;.*//" -e "s/=.*//g" "$base/../python/requirements.txt" | sort | uniq | grep -v "^$" | paste -s -d ,)" --freeze > "$base/../python/requirements-$python_minor_version.txt"

git diff "$base/../python/requirements-$python_minor_version.txt"

