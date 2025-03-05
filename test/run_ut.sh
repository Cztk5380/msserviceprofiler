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

function fn_build_googletest()
{
  cd ${CUR_DIR}/../opensource
  GTEST_DIR="${CUR_DIR}/../opensource/googletest"
  if [ ! -d "$GTEST_DIR" ]; then
      git clone https://codehub-dg-y.huawei.com/OpenSourceCenter/googletest.git googletest -b release-1.12.1
  else
      echo "opensource/googletest already exists. no need to download."
  fi
  if [ ! -d "$GTEST_DIR/googletest-1.12.1" ]; then
    cd googletest
    mkdir gtest_build
    cd gtest_build
    cmake -DCMAKE_INSTALL_PREFIX=$GTEST_DIR/googletest-1.12.1 ..
    make -j20
    make install
  fi
}

run_test_cpp() {
  cd ${TEST_DIR}/..
  bash build.sh
  if [ $? -ne 0 ]; then
    echo "Build ms_service_profiler failed"
    exit 1
  fi
  cd ${TEST_DIR}
  mkdir -p test_build && cd test_build && rm * -rf && cmake ../ut/cpp_test && make -j 4
  if [ $? -ne 0 ]; then
    echo "Build test failed"
    exit 1
  fi
  cd ${TEST_DIR}
  export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${TEST_DIR}/test_build/3rdparty
  (./test_build/st_server_profiler & ./test_build/st_server_profiler) && ./test_build/ut_server_profiler

  if [ $? -ne 0 ]; then
    echo "Run test failed"
    exit 1
  fi

  mkdir -p coverage
  rm -rf ./coverage/*

  lcov_opt="--rc lcov_branch_coverage=1 --rc geninfo_no_exception_branch=1"
  lcov -c -d ./test_build/CMakeFiles/st_server_profiler.dir -o ./coverage/st_server_profiler.info -b ./coverage $lcov_opt
  lcov -c -d ./test_build/CMakeFiles/ut_server_profiler.dir -o ./coverage/ut_server_profiler.info -b ./coverage $lcov_opt
  lcov -a ./coverage/ut_server_profiler.info  -a ./coverage/st_server_profiler.info  -o ./coverage/test_server_profiler.info

  lcov -r ./coverage/test_server_profiler.info '*platform*' -o ./coverage/test_server_profiler.info $lcov_opt
  lcov -r ./coverage/test_server_profiler.info '*opensource*' -o ./coverage/test_server_profiler.info $lcov_opt
  lcov -r ./coverage/test_server_profiler.info '*test*' -o ./coverage/test_server_profiler.info $lcov_opt
  lcov -r ./coverage/test_server_profiler.info '*c++*' -o ./coverage/test_server_profiler.info $lcov_opt
  lcov -r ./coverage/test_server_profiler.info '/usr/include/*' -o ./coverage/test_server_profiler.info $lcov_opt
  lcov -r ./coverage/test_server_profiler.info '*nlohmann*' -o ./coverage/test_server_profiler.info $lcov_opt

  genhtml ./coverage/test_server_profiler.info -o ./coverage/report --branch-coverage
  cd coverage
  tar -zcvf report.tar.gz ./report
  echo show report using cmd: python -m http.server -d ./coverage/report
}

run_test_python() {
  python3 --version
  pip3 install pytest "pandas>=2.2" --default-timeout=20
  export PYTHONPATH=${TOP_DIR}:${PYTHONPATH}
  python3 -m coverage run --branch --source ${TOP_DIR}/'ms_service_profiler' -m pytest ${TEST_DIR}/ut/python_test

  if [ $? -ne 0 ]; then
    echo "UT Failure"
    exit 1
  fi

  python3 -m coverage report -m
  python3 -m coverage xml -o ${TEST_DIR}/coverage.xml
}

run_test() {
  run_test_cpp
  run_test_python
}

main() {
  export VERBOSE=1
  cd ${TEST_DIR}
  fn_build_googletest
  clean
  run_test
  echo "UT Success"
}

main
