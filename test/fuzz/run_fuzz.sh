#!/bin/bash

# 定义项目根目录
PROJECT_DIR=$(pwd)

# 定义构建目录
BUILD_DIR="${PROJECT_DIR}/build"

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
make

# 检查构建是否成功
if [ $? -ne 0 ]; then
    echo "Build failed. Exiting..."
    exit 1
fi

# 运行测试
./msserviceprofiler

# 检查测试是否成功
if [ $? -ne 0 ]; then
    echo "Tests failed. Exiting..."
    exit 1
fi

echo "All tests passed successfully."