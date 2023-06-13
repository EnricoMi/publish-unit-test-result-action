#!/bin/bash

base=$(dirname "$0")

python3 $base/../test_junit.py
python3 $base/../test_nunit.py
python3 $base/../test_xunit.py
python3 $base/../test_trx.py
python3 $base/../test_mocha.py
python3 $base/../test_dart.py
