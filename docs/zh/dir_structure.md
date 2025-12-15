# 项目目录
详细目录介绍如下
```
3rdparty/                                                    # 第三方依赖目录
    ├── CMakeLists.txt                                       # 第三方依赖的根CMakeLists配置文件
    ├── ascend/                                              # 昇腾(Ascend)AI计算平台相关依赖
    │   ├── CMakeLists.txt                                   # 昇腾依赖的CMakeLists配置文件
    │   ├── include/                                         # 头文件目录
    │   │   ├── acl/                                         # Ascend Computing Language头文件
    │   │   │   ├── acl.h                                    # 昇腾计算库主要头文件，用于访问昇腾计算库的各种功能
    │   │   │   └── acl_prof.h                               # 昇腾性能分析头文件
    │   │   ├── mspti/                                       # 昇腾平台工具接口
    │   │   │   └── mspti.h                                  # 昇腾平台工具接口头文件
    │   │   └── mstx/                                        # 昇腾工具扩展
    │   │       └── ms_tools_ext.h                           # 昇腾工具扩展头文件
    │   └── src/                                             # 源码实现目录
    │       ├── BuildAcl.cpp                                 # ACL库构建实现
    │       ├── BuildAclProf.cpp                             # ACL性能分析构建实现
    │       ├── BuildMstx.cpp                                # 昇腾工具扩展构建实现
    │       └── Buildmspti.cpp                               # 昇腾平台工具接口构建实现
    └── opentelemetry/                                       # OpenTelemetry可观测性框架
        ├── include/                                         # OpenTelemetry头文件目录
        └── proto/                                           # Protocol Buffer定义文件
            ├── collector/                                   # 数据收集器相关定义
            │   └── trace/                                   # 追踪数据收集
            │       └── v1/                                  # v1版本
            │           └── trace_service.proto              # 追踪服务协议定义
            ├── common/                                      # 通用定义
            │   └── v1/                                      # v1版本
            │       └── common.proto                         # 通用数据结构定义
            ├── resource/                                    # 资源定义
            │   └── v1/                                      # v1版本
            │       └── resource.proto                       # 资源信息定义
            └── trace/                                       # 追踪相关定义
                └── v1/                                      # v1版本
                    └── trace.proto                          # 追踪数据结构和Span定义
├── CMakeLists.txt                                           # 项目根CMakeLists配置文件
├── README.md                                                # 项目说明文档
└── cpp/                                                     # 基础能力目录（采集），C++源码主目录
    ├── CMakeLists.txt                                       # 数据采集模块，C++模块的CMakeLists配置文件
    ├── include/                                             # 采集能力对外接口目录
    │   └── msServiceProfiler/                               # 数据采集头文件
    │       ├── Config.h                                     # 采集配置文件解析头文件
    │       ├── DBExecutor/                                  # 采集数据落盘模块头文件
    │       │   ├── DbDefines.h                              # 数据库相关常量定义
    │       │   ├── DbExecutorMetaData.h                     # 元数据数据信息落盘头文件
    │       │   ├── DbExecutorMsptiApiData.h                 # MSPTI API数据信息落盘头文件
    │       │   ├── DbExecutorMsptiCommData.h                # MSPTI通用数据信息落盘头文件
    │       │   ├── DbExecutorMsptiMstxData.h                # MSPTI MSTX数据信息落盘头文件
    │       │   ├── DbExecutorMsptikernelData.h              # MSPTI内核数据信息落盘头文件
    │       │   └── DbExecutorServiceData.h                  # 服务化数据信息落盘头文件
    │       ├── DbBuffer.h                                   # 数据库缓冲区管理
    │       ├── Log.h                                        # 日志系统头文件
    │       ├── MultiThreadBufferManager.h                   # 多线程缓冲区管理器
    │       ├── NpuMemoryUsage.h                             # NPU内存数据信息落盘头文件
    │       ├── Profiler.h                                   # 数据采集接口头文件
    │       ├── SecurityConstants.h                          # 安全库相关常量定义
    │       ├── SecurityUtils.h                              # 安全库工具类
    │       ├── SecurityUtilsLog.h                           # 安全库日志模块
    │       ├── ServiceProfilerDbWriter.h                    # 数据落盘写入头文件
    │       ├── ServiceProfilerInterface.h                   # 数据采集对外接口头文件
    │       ├── ServiceProfilerManager.h                     # 数据落盘管理器头文件
    │       ├── ServiceProfilerMspti.h                       # MSPTI数据采集头文件
    │       ├── ServiceTracer.h                              # 服务化Trace追踪头文件
    │       ├── Tracer.h                                     # Trace数据监控对外接口头文件
    │       ├── Utils.h                                      # 通用工具函数
    │       └── msServiceProfiler.h                          # 主入口头文件
    └── src/                                                 # 源文件实现目录
        ├── Config.cpp                                       # 配置文件解析实现
        ├── Log.cpp                                          # 日志系统实现
        ├── NpuMemoryUsage.cpp                               # NPU内存数据信息落盘头实现
        ├── SecurityUtils.cpp                                # 安全库工具类实现
        ├── SecurityUtilsLog.cpp                             # 安全库日志模块实现
        ├── ServiceProfilerDbWriter.cpp                      # 数据落盘写入实现
        ├── ServiceProfilerManager.cpp                       # 数据落盘管理器实现
        ├── ServiceProfilerMspti.cpp                         # MSPTI数据采集实现
        ├── ServiceTracer.cpp                                # 服务追踪器实现
        ├── Tracer.cpp                                       # Trace数据监控接口实现
        └── Utils.cpp                                        # 通用工具函数实现
docs/                                                        # 文档目录
└── zh/                                                      # 中文文档目录
    ├── cpp_api/                                             # C++ API文档
    │   ├── serving_tuning/                                  # 服务化调优API
    │   │   ├── ${api_name}.md                               # API接口说明，${api_name}表示接口名称
    │   │   ├── macro_definitions.md                         # 宏定义说明
    │   │   ├── public_sys-resources/                        # 公共系统资源图标
    │   │   │   ├── icon-${icon-name}.gif                    # 图标，${icon-name}表示图标名称
    │   │   └── serving_tuning.md                            # C++ API文档总说明
    │   └── trace_data_monitoring/                           # Trace追踪数据监控API
    │       ├── ${api_name}.md                               # API接口说明，${api_name}表示接口名称
    │       ├── public_sys-resources/                        # 公共系统资源图标
    │       │   └── ...                                      # 图标文件(同上)
    │       └── sample_code.md                               # 示例代码
    ├── python_api/                                          # Python API文档
    │   ├── README.md                                        # Python API说明
    │   └── context/                                         # 上下文相关API
    │       ├── ${api_name}.md                               # API接口说明，${api_name}表示接口名称
    │       ├── public_sys-resources/                        # 公共系统资源图标
    │       │   └── ...                                      # 图标文件(同上)
    ├── dir_structure.md                                     # 目录结构说明文档
    ├── msserviceprofiler_install_guide.md                   # 安装指南
    ├── msserviceprofiler_serving_tuning_instruct.md         # 服务化调优工具使用说明
    ├── msserviceprofiler_trace_data_monitoring_instruct.md  # Trace监控使用说明
    ├── quick_start.md                                       # 快速开始指南
    ├── release_notes.md                                     # 版本发布说明
    ├── security_statement.md                                # 安全声明
    ├── service_oriented_performance_data_comparison_tool.md # 服务化性能数据比对工具使用指南
    └── vLLM_service_oriented_performance_collection_tool.md # vLLM 服务化性能采集工具使用指南
    ├── figures/                                             # 图表和示意图目录
ms_service_profiler/                                         # 基础能力目录（解析、数据比对等）
    ├── __init__.py                                          # 包初始化文件
    ├── analyze.py                                           # 数据分析主模块
    ├── constant.py                                          # 常量定义文件
    ├── config/                                              # 配置文件目录
    │   ├── msprof_config_sample.json                        # MSProf解析配置文件
    │   └── profiler_visualization.json                      # Grafana可视化配置文件
    ├── data_source/                                         # 数据源导入模块目录
    │   ├── __init__.py                                      # 数据源模块初始化
    │   ├── base_data_source.py                              # 数据源基类
    │   ├── ${name}_source.py                                # ${name}数据源导入模块，name为数据源名称
    └── exporters/                                           # 数据导出器模块目录
        ├── base.py                                          # 导出器基类
        ├── exporter_${name}.py                              # ${name}数据导出器，name为数据名称，例如exporter_batch、exporter_kvcache等
        ├── factory.py                                       # 导出器工厂类
        └── utils.py                                         # 导出器工具函数
ms_service_profiler_ext/                                     # 服务化性能分析能力扩展包
    ├── __init__.py                                          # 包初始化文件
    ├── analyze.py                                           # 扩展分析功能主模块
    ├── compare.py                                           # 数据对比功能主模块
    ├── split.py                                             # 数据拆解功能主模块
    ├── common/                                              # 公共工具模块
    │   ├── __init__.py                                      # 模块初始化
    │   ├── constants.py                                     # 扩展包常量定义
    │   ├── csv_fields.py                                    # CSV字段定义和映射
    │   ├── sec.py                                           # 安全相关工具
    │   ├── split_utils.py                                   # 数据拆解工具函数
    │   └── utils.py                                         # 通用工具函数
    ├── compare_tools/                                       # 数据对比工具模块
    │   ├── __init__.py                                      # 模块初始化
    │   ├── base.py                                          # 对比器基类
    │   ├── collector.py                                     # 数据收集器
    │   ├── compare_visualization.json                       # 对比结果Grafana可视化配置
    │   ├── csv_comparator.py                                # CSV数据对比结果导出
    │   └── db_comparator.py                                 # 数据库据对比结果导出
    ├── exporters/                                           # 扩展导出器模块
    │   ├── __init__.py                                      # 模块初始化
    │   ├── exporter_decode.py                               # decode拆解数据导出器
    │   ├── exporter_prefill.py                              # prefill拆解数据导出器
    │   └── exporter_summary.py                              # 统计数据导出器
    └── split_processor/                                     # 数据拆解处理器模块
        ├── __init__.py                                      # 模块初始化
        ├── base_processor.py                                # 处理器基类
        ├── mindie_processor.py                              # MindIE框架数据处理器
        └── vllm_processor.py                                # vLLM框架数据处理器
    ├── mstx.py                                              # python数据采集模块
    ├── parse.py                                             # 数据解析主模块
    ├── profiler.py                                          # python数据采集接口
    ├── trace.py                                             # 追踪功能主模块
    ├── parse_helper/                                        # 解析辅助工具
    │   ├── __init__.py                                      # 模块初始化
    │   ├── constant.py                                      # 解析相关常量
    │   └── utils.py                                         # 解析工具函数
    ├── pipeline/                                            # 数据处理管道模块
    │   ├── __init__.py                                      # 模块初始化
    │   ├── pipeline_base.py                                 # 管道基类
    │   ├── pipeline_${name}.py                              # ${name}数据处理管道，name为数据名称
    ├── plugins/                                             # 插件系统模块
    │   ├── __init__.py                                      # 模块初始化
    │   ├── base.py                                          # 插件基类
    │   ├── plugin_${name}.py                                # ${name}数据处理插件，name为数据名称
    │   └── sort_plugins.py                                  # 插件排序工具
    ├── processor/                                           # 数据处理器模块
    │   ├── __init__.py                                      # 模块初始化
    │   ├── processor_base.py                                # 处理器基类
    │   ├── processor_${name}.py                             # ${name}数据处理器，name为数据名称
    ├── task/                                                # 任务管理模块
    │   ├── __init__.py                                      # 模块初始化
    │   ├── task.py                                          # 任务定义
    │   ├── task_manager.py                                  # 任务管理器
    │   └── task_register.py                                 # 任务注册器
    ├── tracer/                                              # Trace追踪模块
    │   ├── __init__.py                                      # 模块初始化
    │   ├── binary_otlp_exporter.py                          # 二进制OTLP导出器
    │   ├── otlp_forward_service.py                          # OTLP转发服务
    │   ├── scheduler.py                                     # 调度器
    │   └── socket_server.py                                 # Socket服务器
    ├── utils/                                               # 工具模块
    │   ├── check/                                           # 检查工具
    │   │   ├── checker.py                                   # 检查器基类
    │   │   ├── path_checker.py                              # 路径检查器
    │   │   └── rule.py                                      # 检查规则
    │   ├── constants.py                                     # 全局常量
    │   ├── error.py                                         # 错误处理
    │   ├── file_open_check.py                               # 文件打开检查
    │   ├── log.py                                           # 日志工具
    │   ├── sec.py                                           # 安全工具
    │   ├── secur/                                           # 安全模块
    │   │   ├── __init__.py                                  # 模块初始化
    │   │   ├── constraints/                                 # 安全约束
    │   │   │   ├── __init__.py                              # 约束初始化
    │   │   │   ├── _path.py                                 # 路径约束
    │   │   │   ├── base.py                                  # 约束基类
    │   │   │   ├── helper.py                                # 约束辅助工具
    │   │   │   └── logic.py                                 # 逻辑约束
    │   │   ├── param_validation.py                          # 参数验证
    │   │   └── utils/                                       # 安全工具
    │   │       └── constants.py                             # 安全常量
    │   ├── timer.py                                         # 计时器工具
    │   ├── trace_to_db.py                                   # tarce数据从json格式转为db格式处理模块
    │   └── utils.py                                         # 通用工具函数
    └── vllm_profiler/                                       # vLLM数据采集模块
        ├── __init__.py                                      # 包初始化
        ├── dynamic_hook.py                                  # 动态钩子
        ├── logger.py                                        # 日志记录器
        ├── module_hook.py                                   # 模块钩子
        ├── registry.py                                      # 注册器
        ├── service_profiler.py                              # 服务化数据采集主类
        ├── symbol_watcher.py                                # 符号监视器
        ├── utils.py                                         # 工具函数
        ├── config/                                          # 配置目录
        │   ├── custom_handler_example.py                    # 自定义处理器示例
        │   ├── hooks_example.yaml                           # 钩子配置示例
        │   └── service_profiling_symbols.yaml               # 性能分析符号配置
        ├── vllm_v0/                                         # vLLM v0版本支持
        │   ├── __init__.py                                  # 模块初始化
        │   ├── ${name}_hookers.py                           # ${name}相关函数钩子，${name}为钩子类型名称
        └── vllm_v1/                                         # vLLM v1版本支持
            ├── __init__.py                                  # 模块初始化
            ├── ${name}_hookers.py                           # ${name}相关函数钩子，${name}为钩子类型名称
            └── utils.py                                     # v1版本特定工具函数
├── pyproject.toml                                           # Python项目配置文件
└── test/                                                    # 测试目录
    ├── CMakeLists.txt                                       # C++测试构建配置
    ├── run_st.py                                            # 系统测试运行脚本(Python)
    ├── run_st.sh                                            # 系统测试运行脚本(Shell)
    ├── run_ut.sh                                            # 单元测试运行脚本
    ├── fuzz/                                                # 模糊测试目录
    │   ├── CMakeLists.txt                                   # 模糊测试构建配置
    │   ├── FuzzDefs.h                                       # 模糊测试定义头文件
    │   ├── FuzzMain.cpp                                     # 模糊测试主程序
    │   ├── run_fuzz.sh                                      # 模糊测试运行脚本
    │   └── manager/                                         # 管理模块模糊测试
    │       ├── ${name}_fuzz.cpp                             # ${name}模块模糊测试用例
    ├── st/                                                  # 系统测试(System Test)
    │   ├── cpp/                                             # C++系统测试
    │   │   └── test.cpp                                     # C++测试主程序
    │   └── python/                                          # Python系统测试
    │       ├── __init__.py                                  # 包初始化
    │       ├── conftest.py                                  # Pytest配置
    │       ├── utils.py                                     # 测试工具函数
    │       ├── analyze/                                     # 分析功能测试
    │       ├── checker/                                     # 数据检查模块
    │       ├── collect/                                     # 数据收集测试
    │       ├── executor/                                    # ST执行器模块
    │       ├── multi_analyze/                               # 多服务性能分析测试
    │       ├── profiler/                                    # 性能分析器测试
    │       └── split/                                       # 数据拆解测试
    └── ut/                                                  # 单元测试(Unit Test)
        ├── cpp/                                             # C++单元测试
        │   ├── include/                                     # 头文件目录
        │   │   ├── msptiHelper.h                            # MSPTI辅助工具头文件
        │   │   └── stubs.h                                  # 桩函数头文件
        │   ├── msptiHelper.cpp                              # MSPTI辅助工具测试
        │   ├── test${name}.cpp                              # ${name}模块测试用例，${name}为模块名称
        └── python/                                          # Python单元测试
            ├── data_source/                                 # 数据源测试
            ├── eplb_observe/                                # EPLB观测测试
            ├── task/                                        # 任务管理测试
            ├── trace/                                       # Trace监控模块测试
            ├── test_ms_service_profiler_ext/                # 服务化性能分析扩展能力测试
            ├── test_msguard/                                # 安全模块测试
            ├── test_vllm_profiler/                          # vLLM数据采集能力测试
            └── test_${name}.py                              # ${name}模块测试，${name}为模块名称