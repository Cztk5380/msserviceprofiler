#!/usr/bin/env bash
# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

SHELL_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

export MS_SERVER_PROFILER_HOME=$SHELL_DIR/..
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$SHELL_DIR/../lib
export PYTHONPATH=$PYTHONPATH:$SHELL_DIR/../python
export MS_SERVER_PROFILER_INLUDE_DIR=$SHELL_DIR/../include
export MS_SERVER_PROFILER_LIB_DIR=$SHELL_DIR/../lib

