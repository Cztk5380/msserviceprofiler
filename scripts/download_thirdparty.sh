#!/bin/bash
# This script is used to download thirdpart needed by msserviceprofiler.
# Copyright Huawei Technologies Co., Ltd. 2022-2022. All rights reserved.

set -e

pip install build

CUR_DIR=$(dirname $(readlink -f $0))
TOP_DIR=${CUR_DIR}/..

OPENSOURCE_DIR=${TOP_DIR}/opensource

if [ -n "$1" ]; then
    if [ "$1" == "force" ]; then
        echo "force delete origin opensource files"
        rm -rf ${OPENSOURCE_DIR}/makeself
    fi
fi

function patch_makeself() {
    cd ${OPENSOURCE_DIR}
    git clone --depth=1 -b v2.5.0.x https://gitcode.com/cann-src-third-party/makeself.git
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
[ -d "makeself" ] || patch_makeself
