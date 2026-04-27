# msServiceProfiler 工具安装指南

本文介绍 msServiceProfiler 工具的安装、升级和卸载。

## 安装前准备

- **Python 环境**：需 Python 3.10 及以上版本。可通过以下命令查询版本：

  ```bash
  python --version
  ```

- **CANN 环境**：安装配套版本的 CANN Toolkit 开发套件包和 ops 算子包，并配置 CANN 环境变量，具体请参见[CANN快速安装](https://www.hiascend.com/cann/download)。

- **python 依赖**：可通过以下命令安装：

  ```bash
  pip install -r requirements.txt    # requirements.txt在项目主路径下
  ```

- **sqlite3**：构建依赖 sqlite3，请先安装。示例命令如下：

  ```bash
  apt-get install libsqlite3-dev    # RHEL/CentOS/Fedora 等使用 yum 的系统请执行：yum install sqlite sqlite-devel
  ```

- **lcov**（可选）：如需运行单元测试并统计覆盖率，需额外安装。示例命令如下：

  ```bash
  apt-get install lcov
  ```

## 安装和升级

支持两种方式安装/升级：

- 方式一：从 release 页面下载整包并安装（推荐）。
- 方式二：基于源码构建 run 包并安装。

### 方式一：release 整包下载安装（推荐）

软件安装包发布地址：

- [msserviceprofiler releases](https://gitcode.com/Ascend/msserviceprofiler/releases/)

下载后建议先进行完整性校验（MD5），再执行 `pip install` 安装。示例如下：

```shell
# 1. 下载 release 安装包（以实际发布文件名为准）
wget https://gitcode.com/Ascend/msserviceprofiler/releases/download/<tag>/<package>.whl

# 2. MD5 完整性校验（将 <expected_md5> 替换为 release 页面提供的 MD5）
md5sum <package>.whl
echo "<expected_md5>  <package>.whl" | md5sum -c -

# 3. 安装
pip install <package>.whl
```

> **说明：**
>
> - `<expected_md5>` 请以 release 页面同版本安装包对应的 MD5 值为准。
> - 各版本安装包 MD5 清单请参见[版本说明](./release_notes.md#安装包-md5-校验值)。
> - 若需要升级到指定版本，请先执行 `pip uninstall ms_service_profiler -y`，再安装目标版本 wheel 包。
>
> **MD5sum 校验不一致处理建议：**
>
> - 若 `md5sum -c -` 输出 `FAILED`，请勿继续执行 `pip install`。
> - 请先删除当前下载文件并重新下载，再次执行 MD5 校验。
> - 仍无法通过校验时，请在 release 页面核对文件名与版本是否一致，并通过 Issues 反馈问题。

### 方式二：源码构建 run 包并安装/升级

```shell
# 1. 安装构建依赖
apt-get install libsqlite3-dev  # RHEL/CentOS/Fedora 等使用 yum 的系统请执行：yum install sqlite sqlite-devel

# 2. 拉取源码
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler

# 3. 执行一键构建并升级（自动完成：下载第三方依赖 > 构建 run 包 > 执行安装/升级）

# 方式一：使用环境变量 ASCEND_TOOLKIT_HOME 指定的 CANN 安装路径
bash scripts/build_and_upgrade.sh

# 方式二：手动指定 CANN 安装路径
bash scripts/build_and_upgrade.sh --install-path=/usr/local/Ascend/ascend-toolkit
```

执行时将列出将被覆盖的文件并等待确认，示例回显如下：

```shell
Verifying archive integrity...  100%   SHA256 checksums are OK. All good.
Uncompressing mindstudio-service-profiler  100%  
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: Upgrade target path: /usr/local/Ascend/cann-x.x.x
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: The following files will be overwritten. To keep the original files, please manually copy or backup them.
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler/libms_service_profiler.so
Confirm to proceed? [y/N]: 
```

输入 y 或 Y 确认后，执行成功将有以下回显信息。

```shell
Successfully installed ... ms_service_profiler-x.x.x
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: pip install whl for entry point registration
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: Upgrade completed.
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: mindstudio-msserviceprofiler upgrade completed, the path is: '/usr/local/Ascend/cann-x.x.x'.

[INFO] 构建并升级完成。
```

> **注意：**
>
> - 安装或升级将自动覆盖 CANN 安装路径下的 `ms_service_profiler`、`libms_service_profiler.so`、`include/msServiceProfiler` 等目标文件。如需保留原文件，请根据执行时列出的文件清单提前手动备份。
> - 若未设置 `ASCEND_TOOLKIT_HOME` 且未指定 `--install-path`，将执行失败并提示需手动指定 CANN 安装路径。
> - 若安装中途终止或因依赖缺失等异常终止，请先删除 `msserviceprofiler/build` 目录后再重新执行，命令：`rm -r msserviceprofiler/build`。

## 卸载

```shell
pip uninstall ms_service_profiler -y
```

卸载成功将有以下回显信息。

```shell
Found existing installation: ms_service_profiler x.x.x
Uninstalling ms_service_profiler-x.x.x:
  Successfully uninstalled ms_service_profiler-x.x.x
```
