#!/bin/bash

# 定义项目根目录
PROJECT_DIR=$(pwd)
TOP_DIR="${PROJECT_DIR}/../../"
CMC_URL_COMMON=https://cmc-szver-artifactory.cmc.tools.huawei.com/artifactory/cmc-software-release/Baize%20C/AscendTransformerBoost/1.0.0/asdops_dependency/common

# 定义构建目录
BUILD_DIR="${PROJECT_DIR}/build"

function fn_build_nlohmann_json()
{
  EXTRACT_DIR=${TOP_DIR}/opensource
  if [ -d "$EXTRACT_DIR/json" ]; then
      return $?
  fi

  wget --no-check-certificate $CMC_URL_COMMON/nlohmannjson-v3.11.2.tar.gz
  mkdir -p $EXTRACT_DIR && tar xvf nlohmannjson-v3.11.2.tar.gz -C $EXTRACT_DIR
  mv $EXTRACT_DIR/nlohmannJson $EXTRACT_DIR/json
  rm nlohmannjson-v3.11.2.tar.gz
}

function fn_build_secode_fuzz()
{
  SECODE_DIR="${PROJECT_DIR}/secodefuzz"
  MAKEFILE="${SECODE_DIR}/OpenSource/test/test1/Makefile"
  if [ ! -d "$SECODE_DIR" ]; then
      cd ${PROJECT_DIR}
      git clone https://szv-open.codehub.huawei.com/innersource/Fuzz/secodefuzz.git secodefuzz -b master
  else
      echo "secodefuzz already exists. no need to download."
  fi
  cd ${PROJECT_DIR}/secodefuzz/OpenSource/test/test1
  sed -i "s|CC[[:space:]]*=[[:space:]]*/test/mayp/gcc8.1.0/bin/gcc|CC = /usr/bin/gcc|g" "$MAKEFILE"
  if [ $? -eq 0 ]; then
    echo "CC variable updated successfully in $MAKEFILE."
  else
    echo "Failed to update CC variable in $MAKEFILE."
  fi
  make Secodefuzz_a Secodefuzz_so
  mv ./libSecodefuzz.a ../../../release/lib/Secodefuzz/
  mv ./libSecodefuzz.so ../../../release/lib/Secodefuzz/
  make clean
  make Secodepits_so 
  mv ./libSecodepits.so ../../../release/lib/Secodepits/
}

function fn_build_securec()
{
  mkdir -p ${TOP_DIR}/platform
  SECUREC_DIR="${TOP_DIR}/platform/securec"
  if [ ! -d "$SECUREC_DIR" ]; then
      cd ${TOP_DIR}/platform
      git clone https://codehub-dg-y.huawei.com/hwsecurec_group/huawei_secure_c.git securec -b tag_Huawei_Secure_C_V100R001C01SPC012B002_00001
      cd securec/src
      make
  else
      echo "platform/securec already exists. no need to download."
  fi
}

cd $TOP_DIR
fn_build_nlohmann_json
cd $TOP_DIR
fn_build_securec
cd $PROJECT_DIR
fn_build_secode_fuzz

# 创建构建目录
mkdir -p "${BUILD_DIR}"

# 进入构建目录
cd "${BUILD_DIR}"

# 运行 CMake 配置
cmake ..

# 检查 CMake 配置是否成功
if [ $? -ne 0 ]; then
    echo "CMake configuration failed. Exiting..."
    exit 1
fi

# 构建项目
make -j4

# 检查构建是否成功
if [ $? -ne 0 ]; then
    echo "Build failed. Exiting..."
    exit 1
fi

# 运行测试
./fuzz_msserviceprofiler

# 检查测试是否成功
if [ $? -ne 0 ]; then
    echo "Tests failed. Exiting..."
    exit 1
fi

echo "All tests passed successfully."