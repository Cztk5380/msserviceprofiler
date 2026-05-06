# msServiceProfiler 工具安装指南

## 安装说明

本文介绍 msServiceProfiler 工具的安装、升级和卸载。

支持如下安装方式：

- 使用 run 包安装（推荐）
- 源码编译安装

## 安装前准备

- **Python 环境**：需 Python 3.10 及以上版本。可通过以下命令查询版本：

  ```bash
  python --version
  ```

- **CANN 环境**：请参考《[CANN 快速安装](https://www.hiascend.com/cann/download)》安装昇腾NPU启动和CANN软件（包含Toolkit和ops包）并配置环境变量。

- **python 依赖**：可通过以下命令安装：

  ```bash
  pip install -r requirements.txt    # requirements.txt在项目主路径下
  ```

- **sqlite3**（可选）：如需构建，需安装 sqlite3，请先安装。示例命令如下：

  ```bash
  apt-get install libsqlite3-dev    # RHEL/CentOS/Fedora 等使用 yum 的系统请执行：yum install sqlite sqlite-devel
  ```

- **lcov**（可选）：如需运行单元测试并统计覆盖率，需额外安装。示例命令如下：

  ```bash
  apt-get install lcov
  ```

## 使用 run 包安装

1. 请参考[msServiceProfiler Release](https://gitcode.com/Ascend/msserviceprofiler/releases/)下载msServiceProfiler的run包和对应数字签名文件（.sha256）。

   下载本软件即表示您同意《[华为企业业务最终用户许可协议（EULA）](https://www.hiascend.com/cann/download)》的条款和条件。

2. 验证run包的完整性。

   1. 在run包所在目录执行如下命令获取run包的sha256校验码。

      ```bash
      sha256sum {name}.run
      ```

      打印如下示例信息。

      ```ColdFusion
      {sha256} {name}.run
      ```

   2. 用记事本打开数字签名文件查看sha256校验码。

   3. 比对两个文件的sha256校验码是否一致。

      若两个校验码一致，则表示下载了正确的软件包；若不一致，请不要使用该软件包，需要支持与服务请在论坛求助或提交技术工单。

3. 赋予可执行权限，并用 run 包自检（校验归档完整性与版本依赖）。

   ```bash
   chmod u+x ms-service-profiler-{version}-py3-none-linux_{arch}.run
   ./ms-service-profiler-{version}-py3-none-linux_{arch}.run --check
   ```

4. 安装run包。

   ```bash
   ./ms-service-profiler-{version}-py3-none-linux_{arch}.run --install
   ```

> **说明：**
>
> - 若此前通过 pip 安装过 `ms_service_profiler`，升级到 run 包安装前建议先执行 `pip uninstall ms_service_profiler -y`，避免环境不一致。
> - 若需要升级到指定版本，请下载对应版本的 run 包后执行 `./ms-service-profiler-{version}-py3-none-linux_{arch}.run --upgrade`
> 

## 源码编译安装

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

## 升级

msServiceProfiler 工具升级可参照[使用run包安装](#使用-run-包安装)或[源码编译安装](#源码编译安装)中的步骤直接安装 msServiceProfiler 最新的run包即可，新的run包会自动覆盖原有的run包。

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
