# 服务化性能数据比对工具

## 简介

服务化性能数据比对工具（msServiceProfiler Compare Tool）：用于对比分析大模型推理服务化场景中不同版本或不同框架的性能数据差异，支持生成可视化报告和结构化数据输出。

**基本概念**
- 服务总体维度：包含服务级吞吐量、时延等核心指标
- 请求维度：单个请求的完整处理周期指标
- 批处理维度：批处理任务的分段性能指标

## 使用前准备

**环境准备**
1. 安装Python 3.7+环境：
   ```bash
   python --version  # 验证版本
   ```
2. 安装依赖包：
   ```bash
   pip install "pandas>=2.2" "numpy>=1.24.3"
   ```
3. 安装性能数据采集工具：
   ```bash
   pip install ms_service_profiler
   ```

**约束**
- 仅支持CANN 8.1.RC1及以上版本
- 需配合MindIE 2.0.RC1及以上使用
- 输入数据必须通过ms_service_profiler工具解析生成

## 快速入门

**前提条件**
1. 已完成服务化性能数据采集
2. 准备待比对的input_path和golden_path数据目录

**操作步骤**
1. 执行比对命令：
   ```bash
   ms_service_profiler compare /path/to/input_data /path/to/golden_data
   ```
2. 可选参数配置示例：
   ```bash
   ms_service_profiler compare input_path golden_path \
     --output-path ./custom_result \
     --log-level debug
   ```

## 功能介绍

### 昇腾AI处理器支持情况
> **说明：** 
>AI处理器与昇腾产品的对应关系，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》。

|AI处理器类型|是否支持|
|--|:-:|
|Ascend 910C|√|
|Ascend 910B|√|
|Ascend 310B|√|
|Ascend 310P|√|
|Ascend 910|√|

> **须知：** 
>针对Ascend 910B，当前仅支持该系列产品中的Atlas 800I A2 推理产品。

### 功能说明

提供服务化场景的性能数据差异分析，支持生成：
- Excel格式的结构化比对报告
- Grafana可视化仪表盘数据源
- 多维度（服务级/Request级/Batch级）指标对比

### 命令格式

```
ms_service_profiler compare [options] input_path golden_path
```

### 参数说明

| 参数            | 可选/必选 | 说明                                                         |
|-----------------|-----------|-------------------------------------------------------------|
| input_path      | 必选      | 待分析数据目录（需包含ms_service_profiler解析后的数据）       |
| golden_path     | 必选      | 基准数据目录                                                |
| --output-path   | 可选      | 结果输出目录（默认：./compare_result）                      |
| --log-level     | 可选      | 设置日志级别，取值为：<br>debug：调试级别。该级别的日志记录了调试信息，便于开发人员或维护人员定位问题。<br>info：正常级别。记录工具正常运行的信息。默认值。<br>warning：警告级别。记录工具和预期的状态不一致，但不影响整个进程运行的信息。<br>error：一般错误级别。<br>fatal：严重错误级别。<br>critical：致命错误级别。       |

### 使用示例

```bash
# 执行默认比对
ms_service_profiler compare ./profiling_data/v1 ./profiling_data/v2

# 带自定义输出的比对
ms_service_profiler compare ./data/new ./data/base --output-path ./diff_analysis
```

### 输出结果文件说明

#### 输出目录说明

输出目录结构如下：

```
|- output_path
    |- compare_result.xlsx
    |- compare_result.db
    |- compare_visualization.json
```


|结果文件|说明|
|---|---|
|compare_result.xlsx|展示所有数据 pair 的绝对误差和相对误差。包含有多个标签页，每个标签页以不同维度展示服务化数据|
|compare_result.db|比对结果数据库，用于Grafana数据源|
|compare_visualization.json|用于创建 Grafana 仪表盘|

比对结果支持 Excel 直接展示和 Grafana 可视化，Grafana 可视化参考 https://grafana.org.cn/

#### compare_result.xlsx文件说明

| 标签页       | 内容描述                     | 关键字段                          |
|-------------|----------------------------|----------------------------------|
| Service     | 服务级指标对比              | 吞吐量、平均时延、资源利用率       |
| Request     | 请求级指标对比              | 请求ID、处理阶段耗时、状态码       |
| Batch       | 批处理任务对比              | BatchID、预处理耗时、推理耗时      |

结果示例如下：

|Metric|Data Source|value1|value2|
|---|---|---|---|
|Metric1|input_data|0.9|1.2|
|Metric1|golden_data|1.0|1.0|
|Metric1|Difference|0.1|-10%|0.2|20%|
|Metric2|input_data|0.9|1.2|
|Metric2|golden_data|1.0|1.0|
|Metric2|Difference|0.1|-10%|0.2|20%|

#### Grafana可视化配置

1. 导入compare_visualization.json
2. 配置数据库源为compare_result.db
3. 仪表盘包含：
   - 服务健康度时序图
   - 请求分布热力图
   - 批处理效率对比柱状图

## 附录

### 版本更新日志

| 版本       | 日期         | 更新内容                      |
|-----------|-------------|-----------------------------|
| 1.0.0     | 2025-02-21  | 首次发布基础比对功能            |
