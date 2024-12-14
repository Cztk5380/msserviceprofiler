#!/bin/bash
# This script is used to run ut and st testcase.
# Copyright Huawei Technologies Co., Ltd. 2021-2022. All rights reserved.
CUR_DIR=$(dirname $(readlink -f $0))
TOP_DIR=${CUR_DIR}/..
TEST_DIR=${TOP_DIR}/"test"
SRC_DIR=${TOP_DIR}/"src"
COMPILE_FLAG=0

clean() {
  cd ${TEST_DIR}
  if [ -e ${TEST_DIR}/st_report.xml ]; then
    rm st_report.xml
    echo "remove last st_report success"
  fi

  if [ -e ${TEST_DIR}/report ]; then
    rm -r ${TEST_DIR}/report
    echo "remove last ut_report success"
  fi
}

run_cpp_test() {
  cd ${TEST_DIR}/ut/ait_testcase
  chmod +x ./run_ait_cases.sh
  ./run_ait_cases.sh
}

run_python_test() {
  export PYTHONPATH=${TOP_DIR}:${PYTHONPATH} && python3 run_ut.py
  run_ait
}

run_test() {
  run_cpp_test
  run_python_test
}

main() {
  clean
  local ret=1
  run_test
  ret=$?

  if [ "x"$ret == "x"0 ]; then
    exit 0
  else
    exit 1;
  fi
}

main
