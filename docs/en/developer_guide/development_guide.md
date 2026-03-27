# msServiceProfiler Developer Guide

## Command Line Installation and Build

### Building and Installing msServiceProfiler with pip

Currently, only installation from source is supported.

```shell
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler
pip install .
```

After successful installation, the resulting `libms_service_profiler.so` file is stored in the `msserviceprofiler/build/cp311-cp311-linux_aarch64/cpp` folder.

> Note:<br>
> If installation with `pip` is interrupted (for example, due to missing dependencies), delete the cache directory before retrying.
> The cache directory is located at `msserviceprofiler/build`. To remove it, run `rm -r msserviceprofiler/build`.

## UT Execution

### Prepare for unit tests (UTs)

```shell
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler/test
```

#### Run Python UTs

```shell
bash run_ut.sh python
```

#### Run C++ UTs

```shell
bash run_ut.sh cpp
```
