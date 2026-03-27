# msServiceProfiler Installation Guide

## Installation Description

This document describes how to install, upgrade, and uninstall msServiceProfiler.
If msServiceProfiler is not present in your environment, follow the command-line instructions in [Installation Using the Command Line](#installation-using-the-command-line) to install it. If both CANN Toolkit and msServiceProfiler have been installed, upgrade it as described in [One-Click Build and Upgrade](#one-click-build-and-upgrade). To uninstall the tool, follow the instructions in [Uninstallation](#uninstallation).

## Installation Preparations

### Environment Setup

- Prepare the **Python** environment. Python 3.10 or later is required. To check the Python version:

```bash
python --version
```

- Install the matching CANN Toolkit and ops operator packages, and configure CANN environment variables. For details, see [CANN Installation Guide](https://www.hiascend.com/document/detail/zh/canncommercial/850/softwareinst/instg/instg_0000.html?Mode=PmIns&InstallType=netconda&OS=openEuler).

### Constraints

- Building and installing msServiceProfiler requires sqlite3. To install sqlite3:

```bash
apt-get install libsqlite3-dev
```

- To run unit tests (UTs), install `lcov` for code coverage analysis. The installation command is as follows:

```bash
apt-get install lcov
```

## Installation Using the Command Line

```shell
# Install build dependencies.
apt-get install libsqlite3-dev # On RHEL/CentOS/Fedora, use yum install sqlite sqlite-devel.
# Currently, only source installation is supported.
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler
pip install .
```

A successful installation will show output similar to:

```shell
Successfully built ms_service_profiler
...
Successfully installed ... ms_service_profiler-x.x.x
```

> Note:<br>
> If installation with `pip` is interrupted (for example, due to missing dependencies), delete the cache directory before retrying.
> The cache directory is located at `msserviceprofiler/build`. To remove it, run `rm -r msserviceprofiler/build`.

## Upgrade

Build a `.run` package from source and perform the upgrade. This will automatically overwrite the target files such as `ms_service_profiler`, `libms_service_profiler.so`, and `include/msServiceProfiler` under the CANN Toolkit installation directory.

**Prerequisites**: The tool has been installed with the CANN Toolkit.

### One-Click Build and Upgrade

```shell
# 1. Clone the repository.
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler

# 2. Perform one-click build and upgrade. This automatically downloads third-party dependencies, builds the .run package, and performs the upgrade.

# Method 1: Use `ASCEND_TOOLKIT_HOME` as the upgrade path.
bash scripts/build_and_upgrade.sh

# Method 2: Manually specify an upgrade path.
bash scripts/build_and_upgrade.sh --install-path=/usr/local/Ascend/ascend-toolkit

```

During the upgrade, you will be prompted to confirm the list of files to be overwritten:

```shell
Verifying archive integrity...  100%   SHA256 checksums are OK. All good.
Uncompressing mindstudio-service-profiler  100%  
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: Upgrade target path: /usr/local/Ascend/cann-x.x.x
[mindstudio-msserviceprofiler] [2026-03-04 03:35:37] [INFO]: The following files will be overwritten. To keep the original files, please manually copy or backup them.
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler
  - /usr/local/Ascend/cann-x.x.x/python/site-packages/ms_service_profiler/libms_service_profiler.so
Confirm to proceed? [y/N]: 
```

> Note: The upgrade will automatically overwrite the target files such as `ms_service_profiler`, `libms_service_profiler.so`, and `include/msServiceProfiler` under the upgrade path. Back up any files you wish to keep before proceeding.
>
> Note: If `ASCEND_TOOLKIT_HOME` is not set and `--install-path` is not specified, the upgrade will fail with an error message prompting you to specify a target path.

## Uninstallation

```shell
pip uninstall ms_service_profiler -y
```

If the uninstallation succeeds, the following information is displayed:

```shell
Found existing installation: ms_service_profiler x.x.x
Uninstalling ms_service_profiler-x.x.x:
  Successfully uninstalled ms_service_profiler-x.x.x
```
