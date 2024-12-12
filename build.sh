CUR_DIR=$(dirname $(readlink -f $0))

make_msserviceprofiler() {
    cd $CUR_DIR
    rm -rf build
    mkdir build
    cd build
    cmake ..
    make -j
    cd -
}

make_msserviceprofiler

