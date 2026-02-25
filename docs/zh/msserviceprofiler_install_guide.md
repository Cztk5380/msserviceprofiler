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
#### pip 安装 msserviceprofiler
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
```shell
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler
pip install . --upgrade
```
升级成功将有下述回显信息。
```shell
Successfully built ms_service_profiler
Installing collected packages: ms_service_profiler
  Attempting uninstall: ms_service_profiler
    Found existing installation: ms_service_profiler x.x.x
    Uninstalling ms_service_profiler-x.x.x:
      Successfully uninstalled ms_service_profiler-x.x.x
Successfully installed ms_service_profiler-x.x.x
```
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