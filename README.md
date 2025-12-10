# MindStudio Service Profiler

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
安装msServiceProfiler工具，详情请参见《[msServiceProfiler工具安装指南](docs/zh/msserviceprofiler_install_guide.md)》。

## 🚀[快速入门](docs/zh/quick_start.md)
msServiceProfiler服务化调优工具快速入门。

## 🧰 功能介绍

### [msServiceProfiler服务化调优](docs/zh/msserviceprofiler_serving_tuning_instruct.md)
msServiceProfiler服务化调优工具使用msServiceProfiler接口，采集关键过程的开始和结束时间点，识别关键函数或迭代等信息，记录关键事件，支持多样的信息采集，对性能问题快速定界。

### [vLLM服务化性能采集工具](docs/zh/vLLM_service_oriented_performance_collection_tool.md)
vLLM服务化性能采集工具采集vllm-ascend的服务化框架性能数据以及算子性能数据。

### [Trace数据监控工具](docs/zh/msserviceprofiler_trace_data_monitoring_instruct.md)
Trace数据监控工具采集MindIE-Motor服务中的请求响应时间、响应状态、客户端IP/端口、服务端IP/端口等数据，最后将采集到的数据推送至Jaeger等支持OTLP协议的开源监控平台进行可视化分析。

### [服务化性能数据比对工具](docs/zh/service_oriented_performance_data_comparison_tool.md)
服务化性能数据比对工具支持对使用msserviceprofiler工具采集的性能数据进行差异比对，通过比对快速识别可能存在的问题点。

## ❗免责声明

- 本工具仅供调试和开发之用，使用者需自行承担使用风险，并理解以下内容：

  - [X] 数据处理及删除：用户在使用本工具过程中产生的数据属于用户责任范畴。建议用户在使用完毕后及时删除相关数据，以防泄露或不必要的信息泄露。
  - [X] 数据保密与传播：使用者了解并同意不得将通过本工具产生的数据随意外发或传播。对于由此产生的信息泄露、数据泄露或其他不良后果，本工具及其开发者概不负责。
  - [X] 用户输入安全性：用户需自行保证输入的命令行的安全性，并承担因输入不当而导致的任何安全风险或损失。对于由于输入命令行不当所导致的问题，本工具及其开发者概不负责。
- 免责声明范围：本免责声明适用于所有使用本工具的个人或实体。使用本工具即表示您同意并接受本声明的内容，并愿意承担因使用该功能而产生的风险和责任，如有异议请停止使用本工具。
- 在使用本工具之前，请**谨慎阅读并理解以上免责声明的内容**。对于使用本工具所产生的任何问题或疑问，请及时联系开发者。

## 🔒 安全声明

描述msServiceProfiler产品的安全加固信息、公网地址信息及通信矩阵等内容。详情请参见[msServiceProfiler工具安全声明](docs/zh/security_statement.md)。

## 💬建议与交流

欢迎大家为社区做贡献。如果有任何疑问或建议，请提交issues，我们会尽快回复。感谢您的支持。

🐛 [Issue提交](https://gitcode.com/Ascend/msit/issues)

💬 [昇腾论坛](https://www.hiascend.com/forum/forum-0106101385921175006-1.html)

## ❤️致谢

msServiceProfiler由华为公司的下列部门联合贡献：

- 昇腾计算MindStudio开发部

感谢来自社区的每一个PR，欢迎贡献msServiceProfiler！