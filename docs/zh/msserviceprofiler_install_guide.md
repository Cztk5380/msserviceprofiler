# msServiceProfiler工具安装指南
## 安装说明
本文介绍msServiceProfiler工具的安装，升级和卸载。
## 安装前准备
### 环境准备
- 完整安装采集、解析能力，需准备构建依赖工具 **sickit-build-core**。
- 准备**Python环境**：需要 Python 3.10 或更高版本。
### 约束
- 构建安装依赖 sqlite3, protobuf, json, securec, thread, mindstudio-tools-extension 等模块正常编译安装。
- 如需运行单元测试用例，则需要额外安装 lcov 进行覆盖率统计。安装参考命令行：
```bash
apt-get install lcov
```

## 命令行安装
#### pip 安装 msserviceprofiler
当前只提供源码安装
```shell
git clone https://szv-y.codehub.huawei.com/mindstudio/MindStudio-Backend/msserviceprofiler.git
cd msserviceprofiler
pip install .
```

## 升级
```shell
git clone https://szv-y.codehub.huawei.com/mindstudio/MindStudio-Backend/msserviceprofiler.git
cd msserviceprofiler
pip install . --upgrade
```

## 卸载
```shell
pip uninstall msserviceprofiler -y
```