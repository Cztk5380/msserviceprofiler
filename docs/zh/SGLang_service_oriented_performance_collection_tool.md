# SGLang 服务化性能采集工具使用指南

## 简介

SGLang 服务化性能采集工具（SGLang Service Profiler）是用于监测和采集 SGLang 推理服务框架内部执行流程性能数据的工具。该工具通过采集关键流程的起止时间、识别关键函数、或记录关键事件并捕获多种类型的信息，帮助用户快速定位性能瓶颈。

SGLang Service Profiler 适用于在NPU部署SGLang推理服务过程中进行性能监测和优化分析，覆盖从准备、采集、解析到结果展示的完整流程。

## 产品支持情况

>![](public_sys-resources/icon-note.gif) **说明：** 
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|产品类型| 是否支持 |
|--|:----:|
|Atlas A3 训练系列产品/Atlas A3 推理系列产品|  √   |
|Atlas A2 训练系列产品/Atlas A2 推理系列产品|  √   |
|Atlas 200I/500 A2 推理产品|  x   |
|Atlas 推理系列产品|  x   |
|Atlas 训练系列产品|  x   |
工具支持型号与SGLang框架服务化推理部署支持的NPU型号保持一致，具体可参考 [SGLang installation with NPUs support](https://docs.sglang.io/platforms/ascend_npu.html)。


## 使用前准备
### 环境准备
1. 在昇腾环境安装配套版本的CANN Toolkit开发套件包和ops算子包并配置CANN环境变量，具体请参见《CANN 软件安装指南》。
2. 完成 SGLang 在NPU上的的安装和部署，确保可以正常运行推理服务，具体请参见 [SGLang installation with NPUs support](https://docs.sglang.io/platforms/ascend_npu.html)。

### 约束
- **版本配套**：当前只支持SGLang 0.5.4.post1版本。
- **资源占用**：采集过程中可能占用较大内存，建议根据实际需求调整采集频率参数。

### 安装
1. 源码安装

安装msServiceProfiler工具，详情请参见《[msServiceProfiler工具安装指南](./msserviceprofiler_install_guide.md)》。
工具安装会在当前目录下创建build目录，为编译产物，其中./build/py3-none-linux_aarch64/cpp/libms_service_profiler.so为下一步需要替换的.so文件

2. 替换工具安装包
```bash
# 查找当前CANN Toolkit包路径
find /usr/local/Ascend/ascend-toolkit/ -name libms_service_profiler.so # 其中/usr/local/Ascend/ascend-toolkit/为CANN Toolkit包安装路径
# 多个查找结果中，替换tools目录下的.so文件，例如
cp ./build/py3-none-linux_aarch64/cpp/libms_service_profiler.so /usr/local/Ascend/ascend-toolkit/8.3.RC1/tools/msserviceprofiler/lib/libms_service_profiler.so
```


## 使用说明

**1. 准备采集**

a. 在启动服务前，需要在SGLang框架中导入采集模块。
```bash
# 在SGLang服务化启动入口文件处导入数据采集模块
vim /usr/local/python3.11.13/lib/python3.11/site-packages/sglang/launch_server.py # 其中/usr/local/python3.11.13/lib/python3.11/site-packages为pip show sglang回显的sglang安装路径
# 在原本所有import模块后插入如下代码：
from ms_service_profiler.patcher.sglang import register_service_profiler
register_service_profiler()
```

b. 在启动服务前，需要设置以下环境变量：
- `SERVICE_PROF_CONFIG_PATH`：指定性能分析配置文件路径
- `PROFILING_SYMBOLS_PATH`：指定符号配置文件路径（可选，如不设置默认读取本项目路径下ms_service_profiler/patcher/sglang/config/service_profiling_symbols.yaml文件）


```bash
cd ${path_to_store_profiling_files}
export SERVICE_PROF_CONFIG_PATH=ms_service_profiler_config.json
export PROFILING_SYMBOLS_PATH=service_profiling_symbols.yaml

# 启动 SGLAng 服务
python -m sglang.launch_server --model-path=/Qwen2.5-0.5B-Instruct --device npu
```

其中 `ms_service_profiler_config.json` 为采集配置文件，若不存在会自动生成默认配置。若有需要，可参照[采集配置使用指南](#采集配置使用指南)章节提前进行自定义配置。

`service_profiling_symbols.yaml` 为需要导入的埋点配置文件。你也可以选择不设置环境变量 `PROFILING_SYMBOLS_PATH` ，此时将使用默认的配置文件；若你指定的路径下不存在该文件，系统同样会在你指定的路径生成一份配置文件以便后续修改。可参考[点位配置使用指南](#点位配置使用指南)一节进行自定义。

**2. 开启采集**

将配置文件`ms_service_profiler_config.json`中的 `enable` 字段由 `0` 修改为 `1`，即可开启性能数据采集的开关，可以通过执行下面sed指令完成采集服务的开启：

```bash
sed -i 's/"enable":\s*0/"enable": 1/' ./ms_service_profiler_config.json
```

**3. 发送请求**

根据实际采集需求选择请求发送方式：

```bash
curl http://localhost:30000/v1/completions \
    -H "Content-Type: application/json"  \
    -d '{
         "model": "/Qwen2.5-0.5B-Instruct",
        "prompt": "Beijing is a",
        "max_tokens": 5,
        "temperature": 0
}' | python3 -m json.tool
```

**4. 解析数据**

```bash
# xxxx-xxxx 为采集工具根据 SGLang 启动时间自动创建的存放目录
cd /root/.ms_server_profiler/xxxx-xxxx

# 解析数据
python -m ms_service_profiler.parse --input-path=$PWD
```
更多解析数据命令行参数说明可参考[数据解析](./msserviceprofiler_serving_tuning_instruct.md#数据解析)。

**5. 查看数据**

解析完成后，当前目录下会生成`output`文件夹，其中包含下面表格中列出的交付件：

|          输出件          | 说明                                                                                                         |
|:---------------------:|:-----------------------------------------------------------------------------------------------------------|
| `chrome_tracing.json` | 记录推理服务化请求trace数据，可使用不同可视化工具进行查看，详细介绍请参考[数据可视化](./msserviceprofiler_serving_tuning_instruct.md#数据可视化)       |
|     `profiler.db`     | 用于生成可视化折线图的SQLite数据库文件，详细介绍请参考[ profiler.db 说明](./msserviceprofiler_serving_tuning_instruct.md#profilerdb) |
|     `request.csv`     | 记录服务化推理请求为粒度的详细数据，详细介绍请参考[ request.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#requestcsv)      |
|     `kvcache.csv`     | 记录推理过程的显存使用情况，详细介绍请参考[ kvcache.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#kvcachecsv)          |
|      `batch.csv`      | 记录服务化推理batch为粒度的详细数据，详细介绍请参考[ batch.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#batchcsv)       |

>![](public_sys-resources/icon-note.gif) **说明：**
> 输出结果文件与domain域的采集有强关联关系，具体对照可以参照[domain域与解析结果对照表](./msserviceprofiler_serving_tuning_instruct.md#解析结果)。


## 附录

### 采集配置使用指南
采集配置可以参考[数据采集](./msserviceprofiler_serving_tuning_instruct.md#数据采集)中的配置文件创建的说明以及注意事项的澄清。

### 点位配置使用指南
本工具支持自定义需要采集的函数/方法，支持灵活配置与自定义属性采集。

如需自定义采集点，推荐通过设置环境变量`PROFILING_SYMBOLS_PATH`，将一份点位配置文件复制到工作目录进行修改使用。

**采集点位有更新，需要重启 SGLang 服务加载更新后的配置文件**。

配置文件书写说明及配置示例参考[vLLM 服务化性能采集工具使用指南-点位配置使用指南章节](./vLLM_service_oriented_performance_collection_tool.md#点位配置使用指南)。