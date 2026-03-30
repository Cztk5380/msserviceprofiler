# vLLM 服务化 Prometheus 数据监测工具使用指南

## 简介

vLLM 服务化 Prometheus 数据监测工具用于增强 vLLM-Ascend 推理服务框架的原生监测能力。在 vLLM-Ascend 原生 metrics 基础上，本工具新增以下监测能力：

- **KVCache 监测**：各 DP 域的 block 总数、空闲数、已分配数
- **Token 与吞吐**：各 DP 域的 请求输入/输出 token 数量、总 token 数
- **自定义指标**：支持对任意函数执行时长添加 timer 类型指标

## 产品支持情况

>![](public_sys-resources/icon-note.gif) **说明：** 
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|产品类型| 是否支持 |
|--|:----:|
|Atlas A3 训练系列产品/Atlas A3 推理系列产品|  √   |
|Atlas A2 训练系列产品/Atlas A2 推理系列产品|  √   |
|Atlas 200I/500 A2 推理产品|  √   |
|Atlas 推理系列产品|  √   |
|Atlas 训练系列产品|  x   |

## 使用前准备

### 环境准备

1. 在昇腾环境安装配套版本的CANN Toolkit开发套件包和ops算子包并配置CANN环境变量，具体请参见《[CANN 软件安装指南](https://www.hiascend.com/document/detail/zh/canncommercial/850/softwareinst/instg/instg_0000.html?Mode=PmIns&InstallType=netconda&OS=openEuler)》。
2. 完成 vLLM 和 vLLM-Ascend 的安装和配置并确认 vLLM-Ascend 可以正常运行，metrics端口正常推送数据，具体请参见 [vLLM-Ascend installation](https://vllm-ascend.readthedocs.io/en/latest/installation.html)。

### 约束

- **版本配套**：请确保 vLLM-Ascend、CANN 和采集工具的版本配套关系符合附录中的要求。
- **资源占用**：数据监测必须开启 **Prometheus 多进程模式**（`PROMETHEUS_MULTIPROC_DIR`），可能对推理性能有一定影响。
- **功能限制**：部分高级功能需要特定版本的 vLLM-Ascend 框架支持。

## 使用说明

### 安装

```bash 
pip install ms_service_metric
```

```bash 
# 本地安装（不推荐，仅建议开发时使用）
git clone https://gitcode.com/Ascend/msserviceprofiler.git 
cd msserviceprofiler/ms_service_metric
pip install -e .
```

### 快速开始

按以下顺序操作即可完成指标监测的完整流程：

1. **设置环境变量并启动服务**（含 Prometheus 多进程模式）
2. **开启采集**
3. **发送推理请求**
4. **查看指标**（访问 metrics 端口或接入 Grafana）

### 步骤 1：设置环境变量并启动服务

在启动推理服务前，需设置以下环境变量：

| 环境变量 | 说明 |
|----------|------|
| `MS_SERVICE_METRIC_VLLM_CONFIG` | 符号/埋点配置文件路径（可选，不设置则使用默认配置） |
| `PROMETHEUS_MULTIPROC_DIR` | Prometheus 多进程模式目录（**必填**，需预先创建空目录） |

```bash
# 可选，不设置则使用默认配置
cd ${path_to_store_config_files}
export MS_SERVICE_METRIC_VLLM_CONFIG=service_metrics_symbols.yaml

# 开启 Prometheus 多进程模式（必填）
export PROMETHEUS_MULTIPROC_DIR=/dev/shm/vllm_metrics  # /path/to/your/prometheus/dir
mkdir -p $PROMETHEUS_MULTIPROC_DIR

# 启动 vLLM 服务
vllm serve Qwen/Qwen2.5-0.5B-Instruct &
```

- `service_metrics_symbols.yaml` 为埋点配置，自定义点位请参考[点位配置使用指南](#点位配置使用指南)。
- 8000为vLLM服务化推理启动的默认端口，本文档说明以默认8000端口为例。如需修改服务化启动端口，可在启动 vLLM 服务时通过--port命令行参数指定。更多详细说明可参考[vllm serve命令行参数说明](https://docs.vllm.com.cn/en/latest/cli/serve/#arguments)。

### 步骤 2：开启采集

```bash
# 开启指标采集
ms-service-metric on

# 关闭指标采集
ms-service-metric off

# 重启（重新加载配置）
ms-service-metric restart

# 查看状态
ms-service-metric status
```

### 步骤 3：发送请求

发送推理请求以产生监测数据：

```bash
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "prompt": "Beijing is a",
        "max_tokens": 5,
        "temperature": 0
}' | python3 -m json.tool
```

### 步骤 4：查看指标

通过 vLLM 服务的 metrics 端口获取数据：

```bash
# localhost:8000请替换为服务化运行IP和端口
curl -s http://localhost:8000/metrics
```

也可将 Prometheus 配置为该端口进行抓取，并接入 Grafana 进行可视化。

## 点位配置使用指南

### 功能说明

点位配置文件用于定义需要采集的函数/方法，支持灵活配置与自定义属性采集。

### 注意事项

- 采集点位有更新时，可以通过 `ms-service-metric restart` 重新加载配置。
- 所有自定义指标名会自动添加 `vllm_profiling_` 前缀，且须符合 [Prometheus 指标命名规范](https://prometheus.io/docs/practices/naming/)。

### 配置字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| symbol | Python 导入路径 + 属性链（格式：`模块:类.方法`） | `vllm.v1.core.kv_cache_manager:KVCacheManager.free` |
| min_version | 最低版本约束 | `"0.9.1"` |
| max_version | 最高版本约束 | `"0.11.0"` |
| metrics | 自定义 metric 列表，当前支持 `timer` 类型（采集函数执行时长） | 见下方示例 |

### 配置示例

```yaml
# ===== Custom Metrics =====
- symbol: vllm.entrypoints.openai.serving_chat:OpenAIServingChat.create_chat_completion
  min_version: "0.9.1"
  metrics:
    - name: server:create_chat_completion:duration
      type: timer
```

## 结果说明

### 结果示例

访问 vLLM 服务的 metrics 端口（如 `http://localhost:8000/metrics`）可查看当前监测指标。以下为自定义 `server:create_chat_completion:duration`（timer 类型）的示例输出，可接入 Grafana 等可视化工具进行展示：

```bash
# localhost:8000请替换为服务化运行IP和端口
curl -s http://localhost:8000/metrics | grep -E "server:create_chat_completion:duration"
```

```ColdFusion
# HELP vllm_profiling_server:create_chat_completion:duration Execution duration of server:create_chat_completion:duration
# TYPE vllm_profiling_server:create_chat_completion:duration histogram
vllm_profiling_server:create_chat_completion:duration_sum{dp="-1"} 15.44140076637268
vllm_profiling_server:create_chat_completion:duration_bucket{dp="-1",le="0.001"} 0.0
...
vllm_profiling_server:create_chat_completion:duration_bucket{dp="-1",le="0.2"} 1.0
...
vllm_profiling_server:create_chat_completion:duration_bucket{dp="-1",le="+Inf"} 9.0
vllm_profiling_server:create_chat_completion:duration_count{dp="-1"} 9.0
```

### 内置指标点位说明

以下为工具内置的 metrics 点位。所有指标名前会自动添加 `vllm_profiling_` 前缀，且均包含 `dp` 标签（调度进程为实际 DP 域 ID，请求进程为 `-1`）。

#### 调度与批处理类

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| batch_size | Histogram | 当前正在执行的请求数量 |
| waiting_batch_size | Histogram | 当前等待调度的请求数量 |
| num_spec_tokens | Gauge | 投机解码中的草稿 token 数量 |

#### Token 类

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| total_tokens | Histogram | 单次迭代中 prompt + generation tokens 之和 |
| input | Counter | 输入 prompt 的 token 数量 |
| output | Counter | 输出生成结果的 token 数量 |
| second_token_latency | Histogram | 第二个 token 的生成延迟 |
| fine_grained_ttft | Histogram | 细粒度首 token 延迟（TTFT）|
| fine_grained_tpot | Histogram | 细粒度每 token 平均耗时（TPOT） |

#### KVCache 类

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| total_kvcache_blocks | Gauge | 当前 DP 域 KVCache block 总数 |
| free_kvcache_blocks | Gauge | 当前 DP 域 KVCache 空闲 block 数 |
| allocated_kvcache_blocks | Gauge | 当前 DP 域 KVCache 已分配 block 数 |

>![](public_sys-resources/icon-tip.gif) **提示：** KVCache 使用率可近似计算为 `(1 - free_kvcache_blocks / total_kvcache_blocks) * 100%`，用于监测显存占用与负载均衡。

## 相关文档

- [vLLM 服务化性能采集工具](./vLLM_service_oriented_performance_collection_tool.md)：性能剖析与 Trace 分析
- [数据采集配置说明](./msserviceprofiler_serving_tuning_instruct.md#数据采集)：`ms_service_profiler_config.json` 配置详解
