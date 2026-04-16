#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="${1:-26.0.0}"

cd "${PROJECT_ROOT}"

echo "Building version: ${VERSION}"

# 修改版本号
sed -i.bak "s/^version = .*/version = \"${VERSION}\"/" pyproject.toml

# 打包
python3 -m build --wheel . --outdir "${TOP_DIR:-${PROJECT_ROOT}}/build/output_whl_dir"

# 恢复原文件
mv pyproject.toml.bak pyproject.toml