CUR_DIR=$(dirname $(readlink -f $0))

make_msserviceprofiler() {
    cd $CUR_DIR
    rm -rf build
    mkdir build
    cd build
    cmake ..
    make -j
    rm -rf ../../ms_service_profiler
    cmake --install . --prefix ../../ms_service_profiler
    cd -
}

make_msserviceprofiler

