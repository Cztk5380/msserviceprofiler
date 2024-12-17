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

    mkdir -p output/msserviceprofiler
    cp libms_service_profiler.so output/msserviceprofiler
    cp -r ../ms_service_profiler output

    cd -
}

make_msserviceprofiler

