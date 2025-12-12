# vLLM 服务化性能采集工具使用指南

## 简介

**vLLM Profiler**：vLLM 服务化性能采集工具（vLLM Service Profiler）是用于监控和采集 vLLM-ascend 推理服务框架内部执行流程性能数据的工具。该工具通过采集关键流程的起止时间、识别关键函数或迭代、记录关键事件并捕获多种类型的信息，帮助用户快速定位性能瓶颈。

vLLM Profiler 适用于在 vLLM-ascend 推理服务过程中进行性能监控和优化分析，覆盖从准备、采集、解析到结果展示的完整流程。

### 1. 基本概念

- **性能采集**：通过埋点技术记录服务运行时的关键时间点和事件，生成性能分析数据
- **埋点域（Domain）**：性能数据采集的功能分类，如 Request、KVCache、ModelExecute 等
- **点位配置**：定义需要采集的函数/方法及其属性的配置文件

### 2. 昇腾处理器支持情况
|               产品                | 是否支持 |
|:-------------------------------:|:----:|
| Atlas A3 训练系列产品/Atlas A3 推理系列产品 |  ✅   |
| Atlas A2 训练系列产品/Atlas A2 推理系列产品 |  ✅   |

>![](public_sys-resources/icon-note.gif) **说明：**
> 具体支持情况以 vLLM-ascend 官方支持情况为准：[vLLM-ascend: What devices are currently supported?](https://docs.vllm.ai/projects/ascend/en/latest/faqs.html#what-devices-are-currently-supported)

### 使用前准备
#### 环境准备

1. **部署 vLLM-ascend：** 安装配套版本的 NPU 驱动和固件、CANN 软件（Toolkit、Kernels 和 NNAL）并配置 CANN 环境变量，安装 vLLM、 vLLM-ascend 及他们对应的依赖，具体的安装方式可以参考 [vLLM-Ascend installation](https://vllm-ascend.readthedocs.io/en/latest/installation.html)。在安装完毕之后可以成功启动推理服务。

2. **安装采集工具vLLM Profiler**
  - 方法1：使用 pip 安装 `msserviceprofiler` 包的稳定版本
  
    ```bash
    pip install msserviceprofiler
    ```

  - 方法2：源码安装

    ```bash
    git clone https://gitcode.com/Ascend/msit.git
    cd msit/msserviceprofiler
    pip install -e .
    ```

#### 约束
* 版本配套关系请参考附录中的版本支持表
* 采集过程中可能占用较大内存，建议根据实际需求调整采集频率
* 部分功能需要特定版本的 vLLM-ascend 框架支持

## 快速入门

### 1. 准备采集
在启动服务之前，请设置环境变量 `SERVICE_PROF_CONFIG_PATH` 指定需要加载的性能分析配置文件，并设置环境变量 `PROFILING_SYMBOLS_PATH` 来指定需要导入的符号的 YAML 配置文件。之后，根据您的部署方式启动 vLLM 服务。

```bash
cd ${path_to_store_profiling_files}
# 设置环境变量
export SERVICE_PROF_CONFIG_PATH=ms_service_profiler_config.json
export PROFILING_SYMBOLS_PATH=service_profiling_symbols.yaml

# 启动 vLLM 服务
vllm serve Qwen/Qwen2.5-0.5B-Instruct &
```

其中 `ms_service_profiler_config.json` 为采集配置文件。若指定路径下不存在该文件，将自动生成一份默认配置。若有需要，可参照[采集配置使用指南](#1-采集配置使用指南)章节提前进行自定义配置。

`service_profiling_symbols.yaml` 为需要导入的埋点配置文件。你也可以选择不设置环境变量 `PROFILING_SYMBOLS_PATH` ，此时将使用默认的配置文件；若你指定的路径下不存在该文件，系统同样会在你指定的路径生成一份配置文件以便后续修改。可参考[点位配置使用指南](#2-点位配置使用指南)一节进行自定义。

### 2. 开启采集
将配置文件`ms_service_profiler_config.json`中的 `enable` 字段由 `0` 修改为 `1`，即可开启性能数据采集的开关，可以通过执行下面sed指令完成采集服务的开启：

```bash
sed -i 's/"enable":\s*0/"enable": 1/' ./ms_service_profiler_config.json
```

### 3. 发送请求
根据实际采集需求选择请求发送方式：

```bash
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json"  \
    -d '{
         "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "prompt": "Beijing is a",
        "max_tokens": 5,
        "temperature": 0
}' | python3 -m json.tool
```

### 4. 解析数据
```bash
# xxxx-xxxx 为采集工具根据 vLLM 启动时间自动创建的存放目录
cd /root/.ms_server_profiler/xxxx-xxxx

# 解析数据
msserviceprofiler analyze --input-path=./ --output-path output
```

## 输出结果文件说明

解析完成后，`output` 目录下会生成下面表格中列出的交付件：

|          输出件          | 说明                                                                                                           |
|:---------------------:|:-------------------------------------------------------------------------------------------------------------|
| `chrome_tracing.json` | 记录推理服务化请求trace数据，可使用不同可视化工具进行查看，详细介绍请可以参考[数据可视化](./msserviceprofiler_serving_tuning_instruct.md#数据可视化)       |
|     `profiler.db`     | 用于生成可视化折线图的SQLite数据库文件，详细介绍请可以参考[ profiler.db 说明](./msserviceprofiler_serving_tuning_instruct.md#profilerdb) |
|     `request.csv`     | 记录服务化推理请求为粒度的详细数据，详细介绍请可以参考[ request.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#requestcsv)      |
| `request_summary.csv` | 请求总体统计指标                                                                                                     |
|     `kvcache.csv`     | 记录推理过程的显存使用情况，详细介绍请可以参考[ kvcache.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#kvcachecsv)          |
|      `batch.csv`      | 记录服务化推理batch为粒度的详细数据，详细介绍请可以参考[ batch.csv 说明](./msserviceprofiler_serving_tuning_instruct.md#batchcsv)       |
|  `batch_summary.csv`  | 批次调度总体统计指标                                                                                                   |
| `service_summary.csv` | 服务化维度总体统计指标                                                                                                  |

>![](public_sys-resources/icon-note.gif) **说明：**
> 输出结果文件与domain域的采集有强关联关系，具体对照可以参照[domain域与解析结果对照表](./msserviceprofiler_serving_tuning_instruct.md#解析结果)。

## 功能介绍
### 1 采集配置使用指南
采集配置可以参考[数据采集](./msserviceprofiler_serving_tuning_instruct.md#数据采集)中的配置文件创建的说明以及注意事项的澄清。

>![](public_sys-resources/icon-note.gif) **须知：**
> 目前 vLLM Profiler 暂不支持`torch_prof_stack`，`torch_prof_modules`，`torch_prof_step_num`三项配置的使能。

### 2 点位配置使用指南
点位配置文件用于定义需要采集的函数/方法，支持灵活配置与自定义属性采集。

#### 2.1 文件命名与加载

- 默认加载路径：`~/.config/vllm_ascend/service_profiling_symbols.MAJOR.MINOR.PATCH.yaml`（适用于 vLLM-ascend 框架且文件名随已安装的 vllm 版本变化）
- 备用加载路径：`工具安装路径/msserviceprofiler/vllm_profiler/config/service_profiling_symbols.yaml`

如需自定义采集点，推荐通过设置环境变量`PROFILING_SYMBOLS_PATH`，将一份点位配置文件复制到工作目录进行修改使用。

#### 2.2 配置字段说明

|     字段      | 说明                | 示例                                                    |
|:-----------:|:------------------|:------------------------------------------------------|
|   symbol    | Python 导入路径 + 属性链 | `"vllm.v1.core.kv_cache_manager:KVCacheManager.free"` |
|   handler   | 处理函数类型            | `"timer"`（计时器）或 `"pkg.mod:func"`（自定义）                 |
|   domain    | 埋点域标识             | `"KVCache"`, `"ModelExecute"`                         |
|    name     | 埋点名称              | `"EngineCoreExecute"`                                 |
| min_version | 最低版本约束            | `"0.9.1"`                                             |
| max_version | 最高版本约束            | `"0.11.0"`                                            |
| attributes  | 自定义属性采集           | 只支持 `"timer"` handler。详见下方自定义属性采集机制                   |

#### 2.3 配置示例

- **示例 1：自定义处理函数**

```yaml
- symbol: vllm.v1.core.kv_cache_manager:KVCacheManager.free
  handler: vllm_profiler.config.custom_handler_example:kvcache_manager_free_example_handler
  domain: Example
  name: example_custom
```

- **示例 2：默认计时器**

```yaml
- symbol: vllm.v1.engine.core:EngineCore.execute_model
  domain: ModelExecute
  name: EngineCoreExecute
```

- **示例 3：版本约束**

```yaml
- symbol: vllm.v1.executor.abstract:Executor.execute_model
  min_version: "0.9.1"
  # 未指定 handler -> 默认 timer
```

#### 2.4 自定义属性采集机制

`attributes` 字段支持灵活的自定义属性采集，可对函数参数与返回值进行多种操作与转换。

##### 基本语法

- 参数访问：直接使用参数名，如 `request_id`
- 返回值访问：使用 `return` 关键字
- 管道操作：使用 `|` 分隔多个操作
- 属性访问：使用 `attr` 获取对象属性

##### 配置示例

```yaml
- symbol: vllm_ascend.worker.model_runner_v1:NPUModelRunner.execute_model
  name: ModelRunnerExecuteModel
  domain: ModelExecute
  attributes:
  - name: device
    expr: args[0] | attr device | str
  - name: dp
    expr: args[0] | attr dp_rank | str
  - name: batch_size
    expr: args[0] | attr input_batch | attr _req_ids | len
```

##### 表达式说明

1. `len(input_ids)`：获取 `input_ids` 参数的长度。
2. `len(return) | str`：获取返回值长度并转换为字符串（等价于 `str(len(return))`）。
3. `return[0] | attr input_ids | len`：获取返回值第一个元素的 `input_ids` 属性长度。

##### 支持的表达式类型

- 基础操作：`len()`, `str()`, `int()`, `float()`
- 索引访问：`return[0]`, `return['key']`
- 属性访问：`return | attr attr_name`
- 管道组合：多个操作通过 `|` 连接

##### 高级示例

```yaml
attributes:
  # 获取张量形状
  - name: tensor_shape
    expr: input_tensor | attr shape | str
  
  # 获取字典中的特定值
  - name: batch_size
    expr: kwargs['batch_size']
  
  # 条件表达式（需要自定义处理函数支持）
  - name: is_training_mode
    expr: training | bool
  
  # 复杂的数据处理
  - name: processed_data_len
    expr: data | attr items | len | str
```

#### 2.5 自定义处理函数

当 `handler` 字段指定自定义处理函数时，该函数需满足以下签名：

```python
def custom_handler(original_func, this, *args, **kwargs):
    """
    自定义处理函数
    
    Args:
        original_func: 原始函数对象
        this: 调用对象（对于方法调用）
        *args: 位置参数
        **kwargs: 关键字参数
    
    Returns:
        处理结果
    """
    # 自定义处理逻辑
    pass
```
>![](public_sys-resources/icon-note.gif) **说明：**
> 若自定义处理函数导入失败，系统会自动回退至默认计时器模式。


## 附录

### 1. vLLM各版本及框架支持情况

| 配套CANN版本 | vLLM-ascend V0 | vLLM-ascend V1 |
|:--------:|:--------------:|:--------------:|
| 8.2.RC1  |       /        |  v0.11.0.RC0   |
| 8.2.RC1  |       /        |  v0.10.2.RC1   |
| 8.2.RC1  |       /        |  v0.10.1.RC1   |
| 8.2.RC1  |       /        |  v0.10.0.RC1   |
| 8.2.RC1  |       /        |   v0.9.2.RC1   |
| 8.2.RC1  |     v0.9.1     |     v0.9.1     |
| 8.1.RC1  |   v0.8.5.RC1   |       /        |
| 8.1.RC1  |     v0.8.4     |       /        |
| 8.0.RC3  |     v0.6.3     |       /        |
