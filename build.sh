make_msserviceprofiler() {
    rm -rf build
    mkdir build
    cd build
    cmake ..
    make -j
    cd -
}

make_msserviceprofiler

