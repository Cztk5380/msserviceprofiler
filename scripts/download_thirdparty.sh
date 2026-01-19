#!/bin/bash
# This script is used to download thirdpart needed by msserviceprofiler.
# Copyright Huawei Technologies Co., Ltd. 2022-2022. All rights reserved.

set -e
CUR_DIR=$(dirname $(readlink -f $0))
TOP_DIR=${CUR_DIR}/..

OPENSOURCE_DIR=${TOP_DIR}/opensource
PLATFORM_DIR=${TOP_DIR}/platform
LLT_DIR=${TOP_DIR}/test/opensource

THIRDPARTY_LIST="${OPENSOURCE_DIR}/protobuf    \\
                 ${OPENSOURCE_DIR}/json        \\
                 ${OPENSOURCE_DIR}/makeself    \\
                 ${OPENSOURCE_DIR}/rapidjson    \\
                 ${PLATFORM_DIR}/securec       \\
                 ${LLT_DIR}/googletest         \\
                 ${LLT_DIR}/mockcpp"

if [ -n "$1" ]; then
    if [ "$1" == "force" ]; then
        echo "force delete origin opensource files"
        echo ${THIRDPARTY_LIST}
        rm -rf ${THIRDPARTY_LIST}
    fi
fi

function patch_makeself() {
    cd ${OPENSOURCE_DIR}
    git clone https://gitcode.com/cann-src-third-party/makeself.git
    cd ${OPENSOURCE_DIR}/makeself
    tar -zxf makeself-release-2.5.0.tar.gz
    cd makeself-release-2.5.0
    ulimit -n 8192
    patch -p1 < ../makeself-2.5.0.patch
    cd ${OPENSOURCE_DIR}/makeself
    cp -r makeself-release-2.5.0 ${OPENSOURCE_DIR}
    cd ${OPENSOURCE_DIR}
    rm -rf makeself
    mv makeself-release-2.5.0 makeself
}

mkdir -p ${OPENSOURCE_DIR} && cd ${OPENSOURCE_DIR}
[ ! -d "json" ] && git clone https://gitcode.com/GitHub_Trending/js/json.git json -b v3.11.3
[ ! -d "rapidjson" ] && git clone https://gitcode.com/GitHub_Trending/ra/rapidjson.git rapidjson
[ ! -d "makeself" ] && patch_makeself

mkdir -p ${LLT_DIR} && cd ${LLT_DIR}
[ ! -d "googletest" ] && git clone https://gitcode.com/GitHub_Trending/go/googletest.git googletest -b release-1.12.1
[ ! -d "mockcpp" ] && git clone https://gitcode.com/Ascend/mockcpp.git mockcpp -b ascend_mindstudio_mockcpp_master

mkdir -p ${PLATFORM_DIR} && cd ${PLATFORM_DIR}
[ ! -d "securec" ] && git clone https://gitcode.com/openeuler/libboundscheck.git securec
