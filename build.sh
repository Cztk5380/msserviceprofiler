#!/bin/bash
CUR_DIR=$(dirname $(readlink -f $0))
echo "CUR_DIR=$CUR_DIR"

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

make_msserviceprofiler() {
    cd $CUR_DIR
    fn_build_nlohmann_json
    cd $CUR_DIR
    fn_build_securec
    cd $CUR_DIR
    rm -rf build
    mkdir -p build && cd build && cmake .. && make -j 4 && cmake --install . --prefix output
    cd -
}

make_msserviceprofiler

