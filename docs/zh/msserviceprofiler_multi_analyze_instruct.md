# 服务化多维度解析工具

## 简介
服务化多维度解析工具（msServiceProfiler Multi Analyze）基于msServiceProfiler工具采集的性能数据进行多维度解析，包括request维度、batch维度、总体服务维度。

## 使用前准备

**环境准备**

安装工具，可通过以下两种方式：
- **pip安装**
  ```sh
  pip install -U msserviceprofiler
  msserviceprofiler analyze -h
  ```
- **源码安装**
  ```sh
  git clone https://gitcode.com/Ascend/msit.git
  cd msit/msserviceprofiler
  pip install .[real]
  export PYTHONPATH=$PWD:$PYTHONPATH
  python msserviceprofiler/__main__.py analyze -h
  ```

**版本配套关系**

服务化多维度解析工具，依赖Ascend-cann-toolkit中的ms_service_profiler工具。

| 服务化多维度解析工具 |     CANN     |     MindIE     |
|:-------------:|:------------:|:--------------:|
|     依赖版本      | ≥ 8.1.RC1 | ≥ MindIE 2.0.RC1 |

## 功能介绍

### 功能说明
本工具可对服务化性能数据进行多维度解析。

**注意事项**

无

### 昇腾AI处理器支持情况<a name="ZH-CN_TOPIC_0000002479925980"></a>
>![](public_sys-resources/icon-note.gif) **说明：** 
>AI处理器与昇腾产品的对应关系，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》。

|AI处理器类型|是否支持|
|--|:-:|
|Ascend 910C|x|
|Ascend 910B|√|
|Ascend 310B|x|
|Ascend 310P|√|
|Ascend 910|x|


>![](public_sys-resources/icon-notice.gif) **须知：** 
>针对Ascend 910B，当前仅支持该系列产品中的Atlas 800I A2 推理产品。
>针对Ascend 310P，当前仅支持该系列产品中的Atlas 300I Duo 推理卡+Atlas 800 推理服务器（型号：3000）。

### 命令格式
    ```bash
    python msserviceprofiler/__main__.py analyze 
    --input-path=/path/to/input 
    [--output-path=/path/to/output/]
    [--log-level level]
    [--format format]
    ```

### 参数说明

| 参数             | 可选/必选 | 说明                                                                                                                                                         |
|------------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| --input-path     | 必选      | 指定性能数据所在路径。                                                                                                                                        |
| --output-path    | 可选      | 指定解析后文件生成路径，默认为当前路径下 output 文件夹。                                                                                                      |
| --log-level      | 可选      | 设置日志级别，取值为：<br>- debug：调试级别，记录调试信息，便于定位问题。<br>- info：正常级别，记录工具运行信息。<br>- warning：警告级别，状态不一致但不影响运行。<br>- error：一般错误级别。<br>- fatal：严重错误级别。<br>- critical：致命错误级别。 |
| --format         | 可选      | 设置性能数据输出文件的导出格式，取值为 json、csv、db。                                                                                                        |

### **输出结果文件说明**
- `batch_summary.csv`
  | 字段                 | 说明                                            |
  | -------------------- | ----------------------------------------------- |
  | Metric | 指标项，包含列表头的指标项和行表头的指标数据。  |
  | 指标项（列表头） |
  | prefill_batch_num  | 每个batch中所有batch_type为Prefill的记录数量。 |
  | decode_batch_num  | 每个batch中所有batch_type为Decode的记录数量。 |
  | prefill_exec_time(ms)  | 每个batch中所有batch_type为Prefill modelExec的记录的during_time，若无modelExec，则结果中不含此行，单位ms。 |
  | decode_exec_time(ms)  | 每个batch中所有batch_type为Decode modelExec的记录的during_time，若无modelExec，则结果中不含此行，单位ms。 |
  | 指标数据（行表头）  |
  | Average  | 平均值。  |
  | Max  | 最大值。  |
  | Min  | 最小值。  |
  | P50  | 50%分位数。 |
  | P90  | 90%分位数。 |
  | P99  | 99%分位数。 |
- `request_summary.csv`
  | 字段                 | 说明                                            |
  | -------------------- | ----------------------------------------------- |
  | Metric | 指标项，包含列表头的指标项和行表头的指标数据。  |
  | 指标项（列表头） |
  | first_token_latency(ms)  | 首Token时延，单位ms。 |
  | subsequent_token_latency(ms)  | 非首Token时延，指模型生成第一个Token之后，生成后续每个Token所花费的平均时间，单位ms。 |
  | total_time(ms)  | HTTP请求到结束的总时长，单位ms。 |
  | exec_time(ms)  | modelExec的执行事件，若无modelExec，则结果中不含此行，单位ms。 |
  | waiting_time(ms)  | 请求的等待耗时，单位ms。 |
  | input_token_num  | 每个请求对应的输入Token数量。 |
  | generated_token_num  | 每个请求对应的输出Token数量。 |
  | 指标数据（行表头）  |
  | Average  | 平均值。  |
  | Max  | 最大值。  |
  | Min  | 最小值。  |
  | P50  | 50%分位数。 |
  | P90  | 90%分位数。 |
  | P99  | 99%分位数。 |
- `service_summary.csv`
  | 字段                 | 说明                                            |
  | -------------------- | ----------------------------------------------- |
  | Metric | 指标项，包含列表头的指标项和行表头的指标数据。  |
  | 指标项（列表头） |
  | total_input_token_num  | 总输入Token数量。 |
  | total_generated_token_num  | 总输出Token数量。 |
  | generate_token_speed(token/s)  | 每秒输出Token数，单位token/s。 |
  | generate_all_token_speed(token/s) | 每秒处理Token数，单位token/s （输入输出总数）。 |
  | 指标数据（行表头）  |
  | Value | 具体数值 |
- 采集domain域与解析结果对照表
  | 解析结果                 | 采集domain域                                 |
  | -------------------- | ----------------------------------------------- |
  | batch_summary.csv | "BatchSchedule"。  |
  | request_summary.csv | "Request"。  |
  | service_summary.csv | "Request; BatchSchedule; ModelExecute"。  |
