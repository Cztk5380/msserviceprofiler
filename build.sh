#!/bin/bash
CUR_DIR=$(dirname $(readlink -f $0))
echo "CUR_DIR=$CUR_DIR"
export _GLIBCXX_USE_CXX11_ABI=0

CMC_URL_COMMON=https://cmc-szver-artifactory.cmc.tools.huawei.com/artifactory/cmc-software-release/Baize%20C/AscendTransformerBoost/1.0.0/asdops_dependency/common

function fn_build_nlohmann_json()
{
  EXTRACT_DIR=$CUR_DIR/opensource
  if [ -d "$EXTRACT_DIR/json" ]; then
      return $?
  fi

  wget --no-check-certificate $CMC_URL_COMMON/nlohmannjson-v3.11.2.tar.gz
  mkdir -p $EXTRACT_DIR && tar xvf nlohmannjson-v3.11.2.tar.gz -C $EXTRACT_DIR
  mv $EXTRACT_DIR/nlohmannJson $EXTRACT_DIR/json
  rm nlohmannjson-v3.11.2.tar.gz
}

function fn_build_securec()
{
  mkdir -p ${CUR_DIR}/platform
  SECUREC_DIR="${CUR_DIR}/platform/securec"
  if [ ! -d "$SECUREC_DIR" ]; then
      cd ${CUR_DIR}/platform
      git clone https://codehub-dg-y.huawei.com/hwsecurec_group/huawei_secure_c.git securec -b tag_Huawei_Secure_C_V100R001C01SPC012B002_00001
      cd securec/src
      make
  else
      echo "platform/securec already exists. no need to download."
  fi
}

function fn_build_protobuf()
{
  mkdir -p ${CUR_DIR}/opensource
  PROTOBUF_DIR="${CUR_DIR}/opensource/protobuf"
  if [ ! -d "$PROTOBUF_DIR" ]; then
      cd ${CUR_DIR}/opensource
      wget --no-check-certificate https://cmc.cloudartifact.szv.dragon.tools.huawei.com/artifactory/opensource_general/protobuf/3.21.9/package/protobuf-3.21.9.zip
      rm -rf protobuf-3.21.9
      unzip protobuf-3.21.9.zip
      cd protobuf-3.21.9
      mkdir build
      cd build
      cmake -DCMAKE_INSTALL_PREFIX=../../protobuf -DCMAKE_CXX_FLAGS="-D_GLIBCXX_USE_CXX11_ABI=0" -Dprotobuf_BUILD_TESTS=OFF ..
      make -j 80
      make install
      
  else
      echo "opensource/protobuf already exists. no need to download."
  fi
}

function fn_build_otel_proto()
{
  mkdir -p ${CUR_DIR}/opensource
  OTEL_DIR="${CUR_DIR}/opensource/opentelemetry"
  if [ ! -d "$OTEL_DIR" ]; then
      cd ${CUR_DIR}/opensource
      ./protobuf/bin/protoc ../proto/opentelemetry/proto/trace/v1/trace.proto -I ../proto --cpp_out=./
      ./protobuf/bin/protoc ../proto/opentelemetry/proto/resource/v1/resource.proto -I ../proto --cpp_out=./
      ./protobuf/bin/protoc ../proto/opentelemetry/proto/common/v1/common.proto -I ../proto --cpp_out=./
      ./protobuf/bin/protoc ../proto/opentelemetry/proto/collector/trace/v1/trace_service.proto -I ../proto --cpp_out=./
      
  else
      echo "opensource/opentelemetry already exists. no need to parse."
  fi
}


function add_version()
{
  version_str=`git rev-parse --is-inside-work-tree >/dev/null 2>&1 && echo "$(git rev-parse --abbrev-ref HEAD) $(git log -1 --format='%H %cd' --date=iso)" || echo ""`
  version_file=${CUR_DIR}/build/output/python/ms_service_profiler/analyze.py
  echo $version_file
  if [ -f "$version_file" ]; then
    echo "" >> $version_file
    echo "" >> $version_file
    echo "version='$version_str'" >> $version_file
    echo "" >> $version_file
  fi
}

make_msserviceprofiler() {
    cd $CUR_DIR
    fn_build_nlohmann_json
    cd $CUR_DIR
    fn_build_securec
    cd $CUR_DIR
    fn_build_protobuf
    cd $CUR_DIR
    fn_build_otel_proto
    cd $CUR_DIR
    rm -rf build
    mkdir -p build && cd build && cmake .. && make -j 4 && cmake --install . --prefix output
    add_version
    cd -
}

make_msserviceprofiler
