#!/bin/bash

base=$(dirname "$0")

python $base/../test_junit.py
python $base/../test_nunit.py
python $base/../test_xunit.py
python $base/../test_trx.py
python $base/../test_mocha.py
python $base/../test_dart.py
