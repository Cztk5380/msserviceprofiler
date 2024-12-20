#!/bin/bash
# This script is used to run ut and st testcase.
# Copyright Huawei Technologies Co., Ltd. 2021-2022. All rights reserved.
CUR_DIR=$(dirname $(readlink -f $0))
TOP_DIR=$(readlink -f ${CUR_DIR}/..)
TEST_DIR=${TOP_DIR}/"test"
SRC_DIR=${TOP_DIR}/"src"
ret=0

clean() {
  cd ${TEST_DIR}
  if [ -e ${TEST_DIR}/coverage.xml ]; then
    rm coverage.xml
    echo "remove last coverage.xml success"
  fi
  cd -
}

run_test_cpp() {
  cd .
}

run_test_python() {
  python3 --version
  pip3 install pytest "pandas>=2.2"
  export PYTHONPATH=${TOP_DIR}:${PYTHONPATH}
  python3 -m coverage run --branch --source ${TOP_DIR}/'ms_service_profiler' -m pytest ${TEST_DIR}/ut/python_test
  ret=$(($ret + $?))
  python3 -m coverage report -m
  python3 -m coverage xml -o ${TEST_DIR}/coverage.xml  
}

run_test() {
  run_test_cpp
  run_test_python
}

main() {
  cd ${TEST_DIR}
  clean
  run_test
  if [ "x"$ret == "x"0 ]; then
    echo "UT Success"
    exit 0
  else
    echo "UT Failure"
    exit 1;
  fi
}

main
