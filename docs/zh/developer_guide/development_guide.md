# msServiceProfiler工具开发指南

## 命令行安装编译
#### pip 安装编译 msserviceprofiler
当前只提供源码安装编译
```shell
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler
pip install .
```
安装编译成功后的`libms_service_profiler.so`位于`msserviceprofiler/build/cp311-cp311-linux_aarch64/cpp`文件夹

> 注意：<br>
> 使用 `pip` 安装编译时，如果中途终止安装编译，或者因为安装编译缺失依赖等异常终止，请务必先删除 cache 目录再安装。
> cache 目录位于 `msserviceprofiler/build` 下，参考执行命令：`rm -r msserviceprofiler/build`


## UT执行
#### UT执行准备
```shell
git clone https://gitcode.com/Ascend/msserviceprofiler.git
cd msserviceprofiler/test
```

#### python代码UT执行
```shell
bash run_ut.sh python
```

#### c++代码UT执行
```shell
bash run_ut.sh cpp
```