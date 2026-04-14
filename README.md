# MindStudio Service Profiler

## 📢 最新消息

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

## 📌 简介

本文介绍推理服务化性能数据采集工具，本工具主要使用msServiceProfiler接口，在MindIE和vLLM推理服务化进程中，采集关键过程的开始和结束时间点，识别关键函数或迭代等信息，记录关键事件，支持多样的信息采集，对性能问题快速定位。

## 🔍 目录结构

关键目录如下，详细目录介绍参见[项目目录](docs/zh/dir_structure.md)。

```ColdFusion
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

## 📝 版本说明

| 发布版本 | 发布时间       | 发布Tag       | 兼容性说明    |
| ------- |------------| ------------- | ------------- |
| 26.0.0-alpha.1 | 2026/02/06 | tag_MindStudio_26.0.0-alpha.1 | 兼容昇腾CANN 8.5.0及以前版本。请参考[CANN安装指南](https://www.hiascend.com/cann)获取CANN安装包。 |

## 🛠️ 环境部署

### 环境和依赖

- 硬件环境请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》。

- 工具的使用运行需要提前获取并安装CANN开源版本，当前CANN开源版本正在发布中，敬请期待。

### 工具安装

安装msServiceProfiler工具，详情请参见《[msServiceProfiler工具安装指南](docs/zh/msserviceprofiler_install_guide.md)》。

## 🚀 快速入门

msServiceProfiler服务化调优工具的快速入门，包括必要的操作步骤、参数说明等，具体请参见[快速入门](docs/zh/quick_start.md)。

## 📖 功能介绍

面向不同使用场景，建议按照以下顺序快速体验本工具：

1. **服务化性能调优**：详细理解服务化调优数据格式、可视化分析方式及典型调优流程，参见[服务化调优工具](docs/zh/msserviceprofiler_serving_tuning_instruct.md)。

2. **vLLM / SGLang 场景专项采集**：如只关注某一框架，可直接参考对应服务化性能采集工具使用指南：
    - [vLLM 服务化性能采集工具](docs/zh/vLLM_service_oriented_performance_collection_tool.md)
    - [SGLang 服务化性能采集工具](docs/zh/SGLang_service_oriented_performance_collection_tool.md)

3. **Trace 数据链路监测**：需要将服务端请求链路打通到 Jaeger 等 OTLP 生态时，参见[Trace数据监测工具](docs/zh/msserviceprofiler_trace_data_monitoring_instruct.md)。

4. **采集数据的比对与多维分析**：对不同版本/配置的性能结果做对比或从多维度深入分析时，参见：
    - [服务化性能数据比对工具](docs/zh/ms_service_profiler_compare_tool_instruct.md)
    - [服务化多维度解析工具](docs/zh/msserviceprofiler_multi_analyze_instruct.md)
    - [服务化拆解工具](docs/zh/service_performance_split_tool_instruct.md)

5. **自动寻优与专家建议（进阶能力）**：在已有采集数据基础上进行参数自动寻优或获取专家建议时，参见：
    - [服务化自动寻优工具](docs/zh/serviceparam_optimizer_instruct.md)
    - [服务化自动寻优插件模式](docs/zh/serviceparam_optimizer_plugin_instruct.md)
    - [服务化专家建议工具](docs/zh/service_profiling_advisor_instruct.md)

6. **Prometheus 在线监测（vLLM 场景）**：如需在 vLLM-Ascend 上结合 Prometheus 做在线监控，参见[vLLM 服务化 Prometheus 数据监测工具使用指南](docs/zh/vLLM_metrics_tool_instruct.md)。

## 📝 相关说明

- 《[贡献指南](CONTRIBUTING.md)》
- 《[免责声明](./docs/zh/legal/disclaimer.md)》
- 《[License声明](./docs/zh/legal/license_notice.md)》

## 💬 建议与交流

欢迎大家为社区做贡献。如果有任何疑问或建议，请提交[Issues](https://gitcode.com/Ascend/msserviceprofiler/issues)，我们会尽快回复。感谢您的支持。

- 联系我们

<div>
  <a href="https://raw.gitcode.com/kali20gakki1/Imageshack/raw/main/CDC0BEE2-8F11-477D-BD55-77A15417D7D1_4_5005_c.jpeg">
    <img src="https://img.shields.io/badge/WeChat-07C160?style=for-the-badge&logo=wechat&logoColor=white"></a>
</div>

## 🤝 致谢

msServiceProfiler由华为公司的下列部门联合贡献：

- 昇腾计算MindStudio开发部

感谢来自社区的每一个PR，欢迎贡献msServiceProfiler！ 
