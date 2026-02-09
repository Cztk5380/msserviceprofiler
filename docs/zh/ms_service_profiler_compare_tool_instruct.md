# 服务化性能数据比对工具

## 简介

服务化性能数据比对工具（msServiceProfiler Compare Tool）：用于对比分析大模型推理服务化场景中不同版本或不同框架的性能数据差异，支持生成可视化报告和结构化数据输出。

**基本概念**
- 服务总体维度：包含服务级吞吐量、时延等核心指标
- 请求维度：单个请求的完整处理周期指标
- 批处理维度：批处理任务的分段性能指标

## 产品支持情况
> **说明：** <br>
>昇腾产品的具体型号，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》。

|产品类型| 是否支持 |
|--|:----:|
|Atlas A3 训练系列产品/Atlas A3 推理系列产品|  √   |
|Atlas A2 训练系列产品/Atlas A2 推理系列产品|  √   |
|Atlas 200I/500 A2 推理产品|  √   |
|Atlas 推理系列产品|  √   |
|Atlas 训练系列产品|  x   |

> **须知：** <br>
>针对Atlas A2 训练系列产品/Atlas A2 推理系列产品，当前仅支持该系列产品中的Atlas 800I A2 推理服务器。<br>
>针对Atlas 推理系列产品，当前仅支持该系列产品中的Atlas 300I Duo 推理卡+Atlas 800 推理服务器（型号：3000）。

## 使用前准备

完成[msServiceProfiler工具](msserviceprofiler_install_guide.md)的安装。

**约束**
- 仅支持CANN 8.1.RC1及以上版本。
- 需配合MindIE 2.0.RC1及以上使用。
- 输入数据必须通过msserviceprofiler工具解析生成。

## 快速入门

**前提条件**
1. 已完成服务化性能数据采集
2. 准备待比对的input_path和golden_path数据目录
3. 如果需要算子比对结果，需要输入2个目录下有算子的_ascend_pt结尾的文件

**操作步骤**
1. 执行比对命令：
   ```bash
   msserviceprofiler compare /path/to/input_data /path/to/golden_data
   ```
2. 可选参数配置示例：
   ```bash
   msserviceprofiler compare input_path golden_path \
     --output-path ./custom_result \
     --log-level debug
   ```

## 功能介绍

### 功能说明

提供服务化场景的性能数据差异分析，支持生成：
- Excel格式的结构化比对报告
- 算子比对功能当前仅支持输入目录中包含以“_ascend_pt”为后缀的算子数据文件，请确保输入路径下存在符合此命名规范的目录。

### 命令格式

```
msserviceprofiler compare [options] input_path golden_path --output-path [output-path]
```

### 参数说明

| 参数            | 可选/必选 | 说明                                                         |
|-----------------|-----------|-------------------------------------------------------------|
| input_path      | 必选      | 待分析数据目录（需包含msserviceprofiler解析后的数据）       |
| golden_path     | 必选      | 基准数据目录                                                |
| --output-path   | 可选      | 结果输出目录（默认：./compare_result）                      |
| --log-level     | 可选      | 设置日志级别，取值为：<br>debug：调试级别。该级别的日志记录了调试信息，便于开发人员或维护人员定位问题。<br>info：正常级别。记录工具正常运行的信息。默认值。<br>warning：警告级别。记录工具和预期的状态不一致，但不影响整个进程运行的信息。<br>error：一般错误级别。<br>fatal：严重错误级别。<br>critical：致命错误级别。       |

### 使用示例

```bash
# 执行默认比对
msserviceprofiler compare ./profiling_data/v1 ./profiling_data/v2

```

### 输出结果文件说明

#### 输出目录说明

输出目录结构如下：

```
|- output_path
    |- span_comparation_result.csv
    
```


| 结果文件                        | 说明                                              |
|-----------------------------|-------------------------------------------------|
| span_comparation_result.csv | 展示所有数据 pair 的绝对误差和相对误差。包含有多个span名字，展示不同span时间差异 |



