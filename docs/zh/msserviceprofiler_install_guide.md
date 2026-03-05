# msServiceProfiler工具安装指南

## 安装说明

本文介绍msServiceProfiler工具的安装，升级和卸载。

## 安装前准备

### 环境准备

- 准备**Python环境**：需要 Python 3.10 或更高版本。Python版本查询可使用命令行。

```bash
python --version
```

- 安装配套版本的CANN Toolkit开发套件包和ops算子包并配置CANN环境变量，具体请参见《CANN 软件安装指南》。

### 约束

- 构建安装依赖 sqlite3，安装参考命令行：

```bash
apt-get install libsqlite3-dev
```

- 如需运行单元测试用例，则需要额外安装 lcov 进行覆盖率统计。安装参考命令行：

```bash
apt-get install lcov
```

## 命令行安装

```shell
# 安装构建依赖
apt-get install libsqlite3-dev  # 在RHEL/CentOS/Fedora等使用`yum`的系统上，应使用 yum install sqlite sqlite-devel 
# 当前只提供源码安装
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler
pip install -e .
```

构建安装成功将有下述回显信息。

```shell
Successfully built ms_service_profiler
...
Successfully installed ... ms_service_profiler-x.x.x
```

> 注意：<br>
> 使用 `pip` 安装时，如果中途终止安装，或者因为安装缺失依赖等异常终止，请务必先删除 cache 目录再安装。
> cache 目录位于 `msserviceprofiler/build` 下，参考执行命令：`rm -r msserviceprofiler/build`

## 升级

基于源码构建 run 包并执行升级，将自动覆盖 CANN Toolkit 安装目录下的 `ms_service_profiler`、`libms_service_profiler.so`、`include/msServiceProfiler` 等目标文件。

**前置条件**：已通过安装CANN Toolkit开发套件包完成工具安装。

### 构建 run 包

```shell
# 1. 拉取源码
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler

# 2. 下载三方文件
bash scripts/download_thirdparty.sh

# 3. 构建 run 包（输出至 output/ 目录）
bash scripts/build.sh
```

### 执行升级

```shell
cd output

# 方式一：使用 ASCEND_TOOLKIT_HOME 环境变量
./mindstudio-service-profiler_*.run --upgrade

# 方式二：手动指定升级路径
./mindstudio-service-profiler_*.run --upgrade --install-path=/usr/local/Ascend/ascend-toolkit
```

升级执行时将有下述回显信息，列出将被覆盖的文件并等待用户确认：

```shell
Verifying archive integrity...  100%   SHA256 checksums are OK. All good.
Uncompressing mindstudio-service-profiler  100%  
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: Upgrade target path: /usr/local/Ascend/cann-x.x.x
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: The following files will be overwritten. To keep the original files, please manually copy or backup them.
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler/libms_service_profiler.so
Confirm to proceed? [y/N]: 
```

> 注意：升级将自动覆盖升级路径下的 `ms_service_profiler`、`libms_service_profiler.so`、`include/msServiceProfiler` 等目标文件。如需保留原文件，请在升级前根据升级列表手动备份。
>
> 注意：若未设置 `ASCEND_TOOLKIT_HOME` 且未指定 `--install-path`，升级将失败并提示需手动指定路径。


## 卸载

```shell
pip uninstall ms_service_profiler -y
```

卸载成功将有下述回显信息。

```shell
Found existing installation: ms_service_profiler x.x.x
Uninstalling ms_service_profiler-x.x.x:
  Successfully uninstalled ms_service_profiler-x.x.x
```
