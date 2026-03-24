# ms_service_metric

一个轻量级的 Python 服务指标采集库，支持动态 Hook 和 Prometheus 指标输出。

## 特性

- 🔧 **动态 Hook**: 基于 YAML 配置动态 Hook 目标函数
- 📊 **Prometheus 集成**: 支持 Timer、Counter、Gauge、Histogram 等指标类型
- 🔄 **动态开关**: 通过共享内存和信号实现运行时开关控制
- 🏗️ **框架适配**: 内置 vLLM 框架适配器（SGLang 作为示例参考）
- 🔍 **Locals 访问**: 通过字节码注入访问函数局部变量

## 安装

```bash
pip install ms_service_metric
```

### 依赖

- Python >= 3.10
- pyyaml
- prometheus-client
- posix_ipc (Linux 平台)

## 快速开始

### 1. vLLM 集成

vLLM 通过 entry_points 机制自动适配，无需额外代码：

1. 安装 `ms_service_metric`
2. 启动 vLLM 的多进程 metric 采集环境变量

```bash
# 开启 vLLM 多进程 metric 采集环境变量
export PROMETHEUS_MULTIPROC_DIR=/dev/shm/vllm_metrics && mkdir -p $PROMETHEUS_MULTIPROC_DIR 

# 可选，清理上次的指标文件
# rm -rf $PROMETHEUS_MULTIPROC_DIR/*

# 启动vllm
# vllm serve --model your_model
```

### 2. 控制指标采集

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

### 3. Prometheus + Grafana 可视化 (Windows)

#### 安装 Prometheus

1. 下载 Prometheus Windows 版本:
   - 访问 [Prometheus 下载页面](https://prometheus.io/download/)
   - 下载 `prometheus-<version>.windows-amd64.zip`

2. 解压并配置:
   
   ```powershell
   # 解压到指定目录
   Expand-Archive -Path prometheus-*.zip -DestinationPath C:\Prometheus
   ```

3. 修改 `prometheus.yml` 配置文件，添加 vLLM 指标采集任务:
   
   ```yaml
   scrape_configs:
     - job_name: 'vllm'
       static_configs:
         - targets: ['localhost:8000']
       metrics_path: /metrics
   ```

4. 启动 Prometheus:
   
   ```powershell
   cd C:\Prometheus
   .\prometheus.exe --config.file=prometheus.yml
   ```
   
   Prometheus 默认访问地址: http://localhost:9090

#### 安装 Grafana

1. 下载 Grafana Windows 版本:
   
   - 访问 [Grafana 下载页面](https://grafana.com/grafana/download?platform=windows)
   - 下载并运行安装程序

2. 启动 Grafana 服务:
   
   ```powershell
   # 通过服务管理器启动
   net start grafana
   
   # 或者手动启动
   cd "C:\Program Files\GrafanaLabs\grafana\bin"
   .\grafana-server.exe
   ```

   Grafana 默认访问地址: http://localhost:3000
   - 默认用户名: `admin`
   - 默认密码: `admin`

#### 导入 Dashboard

1. 登录 Grafana Web 界面 (http://localhost:3000)

2. 创建 Prometheus 数据源:
   - 左侧菜单: **Configuration** → **Data sources**
   - 点击 **Add data source**
   - 选择 **Prometheus**
   - URL 填写: `http://localhost:9090`
   - 点击 **Save & Test**

3. 导入 MsServiceMetric Dashboard:
   - 左侧菜单: **Dashboards** → **Import**
   - 点击 **Upload dashboard JSON file**
   - 选择 [Dashboard 样例文件(下载到本地，匹配默认的采集配置)](https://gitcode.com/Ascend/msserviceprofiler/blob/master/ms_service_metric/example/MsServiceMetric-grafana-Dashboard.json) 文件
   - 点击 **Import**   
   - 选择刚才创建的 Prometheus 数据源

### 4. 更多介绍

详细使用方法，请参考：[使用指南](https://gitcode.com/Ascend/msserviceprofiler/blob/master/docs/zh/vLLM_metrics_tool_instruct.md)

## 配置

用户可以自定义需要采集的内容，可以通过：MS_SERVICE_METRIC_VLLM_CONFIG 环境变量指定yaml 文件。如果不指定，默认使用内部的采集配置

### 配置文件格式

创建 YAML 配置文件：

```yaml
# 使用默认 timer handler
- symbol: my_module:MyClass.my_method
  metrics:
    - name: my_method_duration
      type: timer
      labels:
        - name: method
          expr: "ret.method"  # 属性访问

# 使用 counter 统计列表长度
- symbol: my_module:process_batch
  metrics:
    - name: batch_size
      type: counter
      expr: "len(items)"  # 函数调用

# 使用 gauge 记录数值
- symbol: my_module:get_queue_length
  metrics:
    - name: queue_length
      type: gauge
      expr: "queue.size"  # 属性访问

# 使用 histogram 统计耗时分布
- symbol: my_module:process_data
  metrics:
    - name: processing_time
      type: histogram
      expr: "duration"  # 内置变量：执行耗时（秒）
      buckets: [0.001, 0.01, 0.1, 1.0, 10.0]

# 使用自定义 handler（指定 handler 时一般不需要配置 metrics）
- symbol: my_module:complex_process
  handler: my_handlers:custom_handler
```

### 配置项说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 目标符号路径，格式：`module.path:ClassName.method_name` |
| handler | string | 否 | 自定义 handler 路径，格式：`module.path:function_name`。指定 handler 时一般不需要配置 metrics |
| min_version | string | 否 | 最小版本要求 |
| max_version | string | 否 | 最大版本要求 |
| metrics | list | 否 | 指标配置列表（使用默认 handler 时配置）|

### Metrics 配置

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 指标名称 |
| type | string | 是 | 指标类型：timer/counter/gauge/histogram |
| expr | string | 否 | 表达式（非 timer 类型必填） |
| labels | list | 否 | 标签配置 |
| buckets | list | 否 | 直方图分桶（histogram 类型） |

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| MS_SERVICE_METRIC_CONFIG_PATH | 配置文件路径 | 无 |
| MS_SERVICE_METRIC_SHM_PREFIX | 共享内存前缀 | /ms_service_metric |
| MS_SERVICE_METRIC_MAX_PROCS | 最大进程数 | 1000 |
| PROMETHEUS_MULTIPROC_DIR | 多进程指标目录 | 无 |

## Handler 类型

### Wrap Handler

包装函数类型，需要手动调用原函数：

```python
def my_wrap_handler(ori_func, *args, **kwargs):
    # 前置处理
    start_time = time.time()
    
    # 调用原函数
    result = ori_func(*args, **kwargs)
    
    # 后置处理
    duration = time.time() - start_time
    print(f"Duration: {duration}")
    
    return result
```

### Context Handler

上下文管理器类型，使用 yield 控制执行流程。只要使用 context handler，就会自动访问局部变量：

```python
def context_handler(ctx):
    # ctx: FunctionContext 对象
    # ctx.return_value: 返回值（yield 后可用）
    # ctx.locals: 函数的 locals 字典
    
    # 前置处理
    start_time = time.time()
    print(f"Locals before: {ctx.locals}")
    
    yield  # 原函数在这里执行
    
    # 后置处理
    duration = time.time() - start_time
    print(f"Duration: {duration}")
    print(f"Result: {ctx.return_value}")
    print(f"Locals after: {ctx.locals}")
```

**默认 Handler：** 根据配置中是否存在 `expr` 字段自动决定 handler 类型：

- 有 `expr`：创建 context handler（可访问 locals）
- 无 `expr`：创建 wrap handler

**配置示例：**

```yaml
# 使用自定义 context handler（在 handler 中自行处理指标）
- symbol: my_module:complex_function
  handler: my_handlers:context_handler

# 使用默认 handler（有 expr，自动创建 context handler）
- symbol: my_module:another_function
  metrics:
    - name: item_count
      type: counter
      expr: "len(items)"  # items 是函数内的局部变量
```

## 多 Handler 组合

同一个 symbol 可以配置多个 handler，按洋葱模型执行：

```yaml
- symbol: my_module:process
  handler: handlers:auth_check
- symbol: my_module:process
  handler: handlers:timing
  metrics:
    - name: process_duration
      type: timer
```

执行顺序：`auth_check -> timing -> 原函数 -> timing -> auth_check`

## 框架适配

### vLLM

通过 entry_points 自动适配，安装后即可使用，无需额外代码。

### SGLang（示例参考）

> **注意**: SGLang 适配器仅作为示例参考，不作为正式发布功能。

```python
from ms_service_metric.adapters.sglang import initialize_sglang_metric

# 初始化
initialize_sglang_metric()
```

### 自定义适配器

```python
from ms_service_metric.core import SymbolHandlerManager

class MyAdapter:
    def __init__(self):
        self._manager = SymbolHandlerManager()
        
    def initialize(self, config_path: str):
        self._manager.initialize(config_path)
        
    def shutdown(self):
        self._manager.shutdown()
```

## 开发

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest tests/
```

### 代码风格

```bash
black ms_service_metric/
flake8 ms_service_metric/
```

## 架构

```text
┌─────────────────────────────────────────────────────────────┐
│                    SymbolHandlerManager                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ SymbolConfig│  │SymbolWatcher│  │ MetricConfigWatch   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│                    ┌───────────┐                             │
│                    │  Symbol   │                             │
│                    └───────────┘                             │
│                          │                                   │
│              ┌───────────┼───────────┐                       │
│              ▼           ▼           ▼                       │
│         ┌────────┐ ┌────────┐ ┌────────┐                    │
│         │Handler │ │Handler │ │Handler │                    │
│         └────────┘ └────────┘ └────────┘                    │
│              │           │           │                       │
│              └───────────┼───────────┘                       │
│                          ▼                                   │
│                    ┌───────────┐                             │
│                  HookHelper   │                             │
│                    └───────────┘                             │
│                          │                                   │
│                          ▼                                   │
│                    ┌───────────┐                             │
│                 Target Func   │                             │
│                    └───────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

## 安全风险

Metric 数据监测利用了 vllm 的 metric 功能，对外提供接口。[详细参考](https://github.com/vllm-project/vllm/tree/main/examples/online_serving/prometheus_grafana) ，需注意可能存在的安全风险

## 许可证

木兰宽松许可证第2版 (Mulan PSL v2)

## 贡献

欢迎提交 Issue 和 Pull Request。
