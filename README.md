# MindStudio Service Profiler

## 最新消息
- [2025.11.28]：初始化

## 📖简介
本文介绍推理服务化性能数据采集工具，本工具主要使用msServiceProfiler接口，在MindIE和vLLM推理服务化进程中，采集关键过程的开始和结束时间点，识别关键函数或迭代等信息，记录关键事件，支持多样的信息采集，对性能问题快速定界。

## 🗂️目录结构
关键目录如下，详细目录介绍参见[项目目录](docs/zh/dir_structure.md)。
```
├─docs                             # 文档目录
├─include                          # 采集能力对外接口目录
├─ms_service_profiler              # 基础能力目录（解析、数据比对等）
│  ├─tracer                        # Trace数据监控能力目录
│  ├─vllm_profiler                 # vLLM服务化调优能力目录
├─src                              # 基础能力目录（采集）
└─test                             # 测试目录
```

## 🏷️[版本说明](docs/zh/release_notes.md)

包含msserviceprofiler的软件版本配套关系和软件包下载以及每个版本的特性变更说明。

## ⚙️环境部署

### 环境和依赖

- 硬件环境请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》。

- 软件环境请参见《[CANN 软件安装指南](https://www.hiascend.com/document/detail/zh/canncommercial/83RC1/softwareinst/instg/instg_quick.html?Mode=PmIns&InstallType=local&OS=openEuler&Software=cannToolKit)》安装昇腾设备开发或运行环境，即toolkit软件包。

以上环境依赖请根据实际环境选择适配的版本。

## 🛠️工具安装
#### pip 安装 msserviceprofiler
```shell
pip install -U msserviceprofiler
```

## 🚀[快速入门](docs/zh/quickstart.md)
msServiceProfiler服务化调优工具快速入门，包含MindIE框架和vLLM框架。

## 🧰 功能介绍

### [msServiceProfiler服务化调优工具](docs/zh/msServiceProfiler_service_oriented_tuning_tool.md)
msServiceProfiler服务化调优工具使用msServiceProfiler接口，采集关键过程的开始和结束时间点，识别关键函数或迭代等信息，记录关键事件，支持多样的信息采集，对性能问题快速定界。

### [vLLM服务化性能采集工具](docs/zh/vLLM_service_oriented_performance_collection_tool.md)
vLLM服务化性能采集工具采集vllm-ascend的服务化框架性能数据以及算子性能数据。

### [Trace数据监控工具](docs/zh/Trace_data_monitoring_tool.md)
Trace数据监控工具采集MindIE-Motor服务中的请求响应时间、响应状态、客户端IP/端口、服务端IP/端口等数据，最后将采集到的数据推送至Jaeger等支持OTLP协议的开源监控平台进行可视化分析。

### [服务化性能数据比对工具](docs/zh/service_oriented_performance_data_comparison_tool.md)
服务化性能数据比对工具支持对使用msserviceprofiler工具采集的性能数据进行差异比对，通过比对快速识别可能存在的问题点。

## 支持与帮助

🐛 [Issue提交](https://gitcode.com/Ascend/msit/issues)

💬 [昇腾论坛](https://www.hiascend.com/forum/forum-0106101385921175006-1.html)