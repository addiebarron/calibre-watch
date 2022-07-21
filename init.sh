#!/bin/bash

SCRIPT_DIR=$(dirname "$0")
WORKING_DIR=$(pwd)

cd $SCRIPT_DIR
/usr/local/bin/python3 -m pipenv run python ./main.py | /usr/local/bin/ts '[%Y-%m-%d %H:%M:%S]'

