#!/bin/bash
# This script is used to run ut and st testcase.
# Copyright Huawei Technologies Co., Ltd. 2021-2022. All rights reserved.

set -u

CUR_DIR=$(realpath "$(dirname "$0")")

export PYTHONPATH=${PYTHONPATH:-}:${CUR_DIR}/st/python

python -m unittest discover ${CUR_DIR}/st/python/collect

unset PYTHONPATH

