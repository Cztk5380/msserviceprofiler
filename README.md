# MindStudio Service Profiler
## 最新消息
- [2025.12.30] 支持Torch Profiler数据采集，解析。
- [2025.11.30] 支持与OpenTelemetry开源生态对接，进行Trace数据追踪。
- [2025.11.24] 支持无侵入式自动插桩采集vLLM框架服务化性能数据。
- [2025.11.07] 支持自动寻优插件化模式。
- [2025.09.30] 支持A2单机进行MindIE的PD分离自动寻优。
- [2025.09.30] 支持自动寻优微调能力，提升自动寻优搜索效率。
- [2025.09.30] 支持算子通信数据采集，解析。
- [2025.09.30] 支持coordinator，流式请求返回服务化性能数据采集。
- [2025.09.30] 支持服务化性能数据解析生成请求推理forward.csv，请求状态request_status.csv表。
- [2025.09.30] 支持MindIE动态负载均衡专家负载热力图分析。
- [2025.08.25] 支持vLLM-v1服务化框架性能数据采集，解析。

## 简介
本文介绍推理服务化性能数据采集工具，本工具主要使用msServiceProfiler接口，在MindIE和vLLM推理服务化进程中，采集关键过程的开始和结束时间点，识别关键函数或迭代等信息，记录关键事件，支持多样的信息采集，对性能问题快速定位。

## 目录结构
关键目录如下，详细目录介绍参见[项目目录](docs/zh/dir_structure.md)。
```
├─docs                             # 文档目录
├─include                          # 采集能力对外接口目录
├─ms_service_profiler              # 基础能力目录（解析、数据比对等），python源码主目录
│  ├─tracer                        # Trace数据监测能力目录
│  ├─patcher                       # vLLM服务化调优能力目录
├─msservice_advisor/               # 专家建议工具目录
├─ms_serviceparam_optimizer/                  # 自动寻优工具目录
└── cpp                            # 基础能力目录（采集），C++源码主目录
└─test                             # 测试目录
```

## 环境部署

### 环境和依赖

- 硬件环境请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》。

- 工具的使用运行需要提前获取并安装CANN开源版本，当前CANN开源版本正在发布中，敬请期待。

## 工具安装
安装msServiceProfiler工具，详情请参见《[msServiceProfiler工具安装指南](docs/zh/msserviceprofiler_install_guide.md)》。

## 快速入门
msServiceProfiler服务化调优工具的快速入门，包括必要的操作步骤、参数说明等，具体请参见[快速入门](docs/zh/quick_start.md)。

##  功能介绍

### [服务化调优工具](docs/zh/msserviceprofiler_serving_tuning_instruct.md)
服务化调优工具使用msServiceProfiler接口，采集关键过程的开始和结束时间点，识别关键函数或迭代等信息，记录关键事件，支持多样的信息采集，对性能问题快速定位。

### [vLLM服务化性能采集工具](docs/zh/vLLM_service_oriented_performance_collection_tool.md)
vLLM服务化性能采集工具采集vLLM-Ascend的服务化框架性能数据以及算子性能数据。

### [Trace数据监测工具](docs/zh/msserviceprofiler_trace_data_monitoring_instruct.md)
Trace数据监测工具采集MindIE Motor服务中的请求响应时间、响应状态、客户端IP/端口、服务端IP/端口等数据，最后将采集到的数据推送至Jaeger等支持OTLP协议的开源监测平台进行可视化分析。

### [服务化性能数据比对工具](docs/zh/ms_service_profiler_compare_tool_instruct.md)
服务化性能数据比对工具支持对使用msServiceProfiler工具采集的性能数据进行差异比对，通过比对快速识别可能存在的问题点。

### [服务化自动寻优工具](docs/zh/serviceparam_optimizer_instruct.md)
基于msServiceProfiler工具采集的性能数据，提供服务化参数自动寻优能力，可以对服务化的参数以及测试工具的参数进行寻优。具体请参见服务化自动寻优工具。

### [服务化专家建议工具](docs/zh/service_profiling_advisor_instruct.md)
基于benchmark 输出结果以及 service 的 config.json 配置，提供分析提高 TTFT / Throughput 等的优化点能力。具体请参见服务化专家建议工具。

### [服务化多维度解析工具](docs/zh/msserviceprofiler_multi_analyze_instruct.md)
基于msServiceProfiler工具采集的性能数据，提供性能数据多维度分析能力，可以对性能数据进行batch维度、request维度和service维度分析。具体请参见服务化多维度解析工具。

### [服务化拆解工具](docs/zh/service_performance_split_tool_instruct.md)
基于msServiceProfiler工具采集的性能数据，提供性能数据拆解能力，可以对batch内各阶段耗时进行分析。具体请参见服务化拆解工具。

## 贡献指导
介绍如何向msServiceProfiler反馈问题、需求以及为msServiceProfiler贡献的代码开发流程，具体请参见[为MindStudio ServiceProfiler贡献](CONTRIBUTING.md)。

## 联系我们

<div>
  <a href="https://raw.gitcode.com/kali20gakki1/Imageshack/raw/main/CDC0BEE2-8F11-477D-BD55-77A15417D7D1_4_5005_c.jpeg">
    <img src="https://img.shields.io/badge/WeChat-07C160?style=for-the-badge&logo=wechat&logoColor=white"></a>
</div>

## 免责声明
### 致msServiceProfiler使用者

1. 对于msServiceProfiler测试用例以及示例文件中所涉及的各模型和数据集，平台仅用于功能测试，华为不提供任何模型权重和数据集，如您使用这些数据进行训练/推理，请您特别注意应遵守对应模型和数据集的License，如您因使用这些模型和数据集而产生侵权纠纷，华为不承担任何责任。
2. 如您在使用msServiceProfiler过程中，发现任何问题（包括但不限于功能问题、合规问题），请在GitCode提交Issue，我们将及时审视并解决。
3. msServiceProfiler功能依赖的opentelemetry等第三方开源软件，均由第三方社区提供和维护，因第三方开源软件导致的问题的修复依赖相关社区的贡献和反馈。您应理解，msServiceProfiler仓库不保证对第三方开源软件本身的问题进行修复，也不保证会测试、纠正所有第三方开源软件的漏洞和错误。
4. 对于您在使用msServiceProfiler功能过程中产生的数据属于用户责任范畴。建议您在使用完毕后及时删除相关数据，以防泄露或不必要的信息泄露。
5. 对于您在使用msServiceProfiler功能过程中产生的数据，建议您避免通过本工具随意外发或传播，对于因此产生的信息泄露、数据泄露或其他不良后果，华为不承担任何责任。
6. 对于您在使用msServiceProfiler功能过程中输入的命令行，需要您自行保证的命令行安全性，并承担因输入不当而导致的任何安全风险或损失。对于由于输入命令行不当所导致的问题，华为不承担任何责任。

### 致数据所有者

如果您不希望您的模型或数据集等信息在msServiceProfiler中被提及，或希望更新msServiceProfiler中有关的描述，请在GitCode提交issue，我们将根据您的issue要求删除或更新您相关描述。衷心感谢您对msServiceProfiler的理解和贡献。


## License
msServiceProfiler产品的使用许可证，具体请参见[LICENSE](./LICENSE)。<br>
msServiceProfiler工具docs目录下的文档适用CC-BY 4.0许可证，具体请参见[LICENSE](./docs/LICENSE)。

## 贡献声明
1. 提交错误报告：如果您在msServiceProfiler中发现了一个不存在安全问题的漏洞，请在msServiceProfiler仓库中的Issues中搜索，以防该漏洞被重复提交，如果找不到漏洞可以创建一个新的Issues。如果发现了一个安全问题请不要将其公开，请参阅安全问题处理方式。提交错误报告时应该包含完整信息。
2. 安全问题处理：本项目中对安全问题处理的形式，请通过邮箱通知项目核心人员确认编辑。
3. 解决现有问题：通过查看仓库的Issues列表可以发现需要处理的问题信息, 可以尝试解决其中的某个问题。
4. 如何提出新功能：请使用Issues的Feature标签进行标记，我们会定期处理和确认开发。
5. 开始贡献：<br>
    a. Fork本项目的仓库。<br>
    b. Clone到本地。<br>
    c. 创建开发分支。<br>
    d. 本地自测：提交前请通过所有的单元测试，包括新增的单元测试。<br>
    e. 提交代码。<br>
    f. 新建Pull Request。<br>
    g. 代码检视：您需要根据评审意见修改代码，并再次推送更新。此过程可能会有多轮。<br>
    h. 当您的PR获得足够数量的检视者批准后，Committer会进行最终审核。<br>
    i. 审核和测试通过后，CI会将您的PR合并入到项目的主干分支。<br>

## 安全声明

描述msServiceProfiler产品的安全信息、公网地址及通信矩阵等信息，具体内容请参见[msServiceProfiler工具安全声明](docs/zh/security_statement.md)。

## 建议与交流

欢迎大家为社区做贡献。如果有任何疑问或建议，请提交[Issues](https://gitcode.com/Ascend/msserviceprofiler/issues)，我们会尽快回复。感谢您的支持。

## 致谢

msServiceProfiler由华为公司的下列部门联合贡献：

- 昇腾计算MindStudio开发部

感谢来自社区的每一个PR，欢迎贡献msServiceProfiler！ 