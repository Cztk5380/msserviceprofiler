# msServiceProfiler工具安装指南
## 安装说明
本文介绍msServiceProfiler工具的安装，升级和卸载。
## 安装前准备
### 环境准备
- 完整安装采集、解析能力，需准备构建依赖工具 **scikit-build-core**。
- 准备**Python环境**：需要 Python 3.10 或更高版本。
### 约束
- 构建安装依赖 sqlite3，安装参考命令行。
```bash
apt-get install libsqlite3-dev
```

- 如需运行单元测试用例，则需要额外安装 lcov 进行覆盖率统计。安装参考命令行：
```bash
apt-get install lcov
```

## 命令行安装
#### pip 安装 msserviceprofiler
当前只提供源码安装
```shell
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler
pip install .
```

> 注意：<br>
> 使用 `pip` 安装时，如果中途终止安装，或者因为安装缺失依赖等异常终止，请务必先删除 cache 目录再安装。
> cache 目录位于 `msserviceprofiler/build` 下，参考执行命令：`rm -r msserviceprofiler/build`

## 升级
```shell
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler
pip install . --upgrade
```

## 卸载
```shell
pip uninstall ms_service_profiler -y
```