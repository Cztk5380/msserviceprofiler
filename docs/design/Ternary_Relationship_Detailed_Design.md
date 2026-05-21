# 三元关系详设

## 修订记录

| 日期 | 修订版本 | 修改描述 | 作者 | RFC文档 |
| -- | -- | -- | -- | -- |
| 2026-05-16 | 1.0 | 初稿完成 | 待确认 | 待确认 |
| 2026-04-27 | 1.1 | 新增 `-c/--config` 命令行参数，支持用户在启动时显式指定配置文件路径 | 待确认 | 待确认 |

## 背景描述

服务化自动寻优工具通过 `OptimizerConfigField` 描述可调参数，再由 `map_param_with_value` 将 PSO 粒子位置解码为实际运行参数。已有参数关系支持基础类型、枚举、比例、二元派生等场景，但在模型并行配置中，经常存在三个参数共同满足乘积约束的关系，例如 `tp * pp * dp = world_size`，单纯用二元 `factories` 无法表达两个源字段共同决定一个派生字段的场景。

当前痛点主要有三类。第一，复杂参数关系需要在配置或插件中绕行处理，导致不同框架的实现方式不一致。第二，当 PSO 生成的 `tp`、`pp` 等源字段组合不能整除或使派生值越界时，简单截断会产生不自洽配置，例如 `tp * pp * dp != product`。第三，约束修复如果固定单一方向，会让某一类源字段长期优先被保留，影响搜索空间覆盖和结果公平性。

本特性引入三元关系参数推导能力，支持 `ternary_factories` 和 `ternary_times` 两类派生字段，并为三元除法提供优先级感知的约束修复策略。核心价值是把复杂并行关系沉淀到统一的配置字段模型中，减少插件重复逻辑，并保证实际执行参数与 PSO 内部粒子位置保持一致。

随着工具功能持续扩展（三元关系、健康检查、多模型配置等），`config.toml` 所承载的配置项快速增多，用户需要同时管理多份针对不同模型、集群或场景的配置文件。当前唯一的绕行方案是修改环境变量 `MODEL_EVAL_STATE_CONFIG_PATH`，但对命令行一次性调用不友好，且每次切换配置需要额外 `export`。因此，本项目同步新增 `-c/--config` 命令行参数，使用户可将配置文件放在任意路径并在启动时直接指定。

目标如下：

- 支持通过 `dtype="ternary_factories"` 表达 `value = product / (field_a * field_b)`。
- 支持通过 `dtype="ternary_times"` 表达 `value = product * field_a * field_b`。
- 当三元除法结果越界或非整除时，优先通过调整源字段生成自洽参数组合。
- 支持 `fixed` 和 `balanced` 两种修复优先级策略，降低 PSO 搜索中的结构性偏置。
- 将修复后的真实参数位置回写给 PSO，使 `personal_best`、`global_best` 基于实际评估参数。
- 支持通过 `-c/--config` 命令行参数指定任意路径的配置文件，该文件具有最高优先级。

非目标如下：

- 不改变现有 `int`、`float`、`bool`、`enum`、`ratio`、`share`、`factories`、`times` 的语义。
- 不在本特性中引入通用约束求解器，第一版仅支持两个源字段的三元关系。
- `-c/--config` 参数暂不支持同时传入多个配置文件，不对其他子命令（如 `source_to_train`）添加同等参数。

## 方案设计

### 场景用例

典型用例是自动寻优需要同时搜索 `tp` 和 `pp`，并自动推导 `dp`。用户或插件在 `target_field` 中定义 `tp`、`pp` 为可搜索字段，定义 `dp` 为三元派生字段：

```toml
[[mindie.target_field]]
name = "tp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.tp"
min = 0
max = 1
dtype = "enum"
dtype_param = [1, 2, 4, 8]

[[mindie.target_field]]
name = "pp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.pp"
min = 0
max = 1
dtype = "enum"
dtype_param = [1, 2, 4]

[[mindie.target_field]]
name = "dp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.dp"
min = 0
max = 0
dtype = "ternary_factories"
dtype_param = { target_names = ["tp", "pp"], product = 32, dtype = "int", min_value = 1, priority_policy = "balanced" }
```

PSO 只搜索非派生字段，运行前由 `map_param_with_value` 统一完成三元推导和约束修复。派生字段通常配置为 `min = max = 0`，由 `OptimizerConfigField.update_constant` 标记为常量，从而不占用粒子维度。

另一典型用例是用户在 `/data/configs/` 目录下维护了针对不同模型的多份配置文件，启动寻优时不想将文件拷贝到默认路径：

```bash
# 针对 GLM-5.1 的寻优，使用项目配置目录下的配置
msserviceprofiler optimizer -e vllm -b vllm_benchmark -c /data/configs/glm_config.toml

# 切换到另一个模型的配置，无需修改环境变量
msserviceprofiler optimizer -e vllm -b vllm_benchmark -c /data/configs/qwen_config.toml
```

工具解析 `-c` 参数后，验证文件存在且为合法 TOML，将该文件追加到配置加载列表末尾（最高优先级），其他未覆盖的配置项仍从默认路径继承。

### 整体思路

本特性在 `ms_serviceparam_optimizer/ms_serviceparam_optimizer/config/config.py` 中扩展参数字段模型和解码流程。`OptimizerConfigField` 新增三元派生类型说明，`update_optimizer_value` 在已有二元派生处理后增加 `ternary_factories` 和 `ternary_times` 分支。

三元除法的关键问题是自洽性。对于 `int` 类型，`product / (field_a * field_b)` 如果不能整除，直接 `int()` 截断会破坏乘积关系。因此实现将“非整除、低于下界、高于上界”统一视为需要修复的场景，先尝试约束修复，再在不可修复时按明确策略降级。

PSO 路径需要额外保证“评估参数”和“粒子位置”一致。`PSOOptimizer.op_func` 为每个粒子构造 `DecodeContext`，调用 `map_param_with_value` 预解码并通过 `field_to_param` 把修复后的真实参数反写到 `x[i]`。随后 `Scheduler.run_with_request_rate` 使用同一个 `DecodeContext` 运行评估，避免 PSO 认为评估的是原始非法位置。

### 系统架构

![image.png](https://raw.gitcode.com/user-images/assets/8473562/67bca396-5c5d-4304-bb1b-1fe7417cd94c/image.png 'image.png')

该架构把三元关系集中在参数配置解码层，服务框架和测试工具只接收最终参数，不需要感知三元推导细节。

### 核心流程

![image.png](https://raw.gitcode.com/user-images/assets/8473562/7526ccd0-40df-43dd-ac22-422a78f3dbda/image.png 'image.png')

该流程覆盖主路径、依赖字段缺失、依赖字段非法、结果越界、非整除和修复失败等关键分支。

### 约束修复策略

三元除法修复由 `_repair_ternary_factories_with_priority` 完成，输入为派生字段定义、当前运行字段、原始字段定义、`product`、上下界、类型转换函数和可选 `DecodeContext`。

修复分两阶段：

1. 阶段一固定高优先级字段 `keep`，只在低优先级字段 `adjust` 的候选值中搜索最近合法值。
2. 阶段二在两个字段候选集中按与当前值的距离排序后联合搜索，选择第一组合法组合。

合法组合必须满足：

- 两个源字段均非 0。
- `int` 类型下 `product % (field_a * field_b) == 0`。
- 推导结果不小于 `min_value`，不大于 `max_value`。

优先级由 `resolve_priority` 解析：

| 策略 | 配置 | 行为 |
| -- | -- | -- |
| `fixed` | `priority_policy="fixed"`，可选 `priority=["tp","pp"]` | 按显式 `priority` 保留高优先级字段；配置缺失或非法时退化为 `target_names` 顺序 |
| `balanced` | `priority_policy="balanced"` 或缺省 | PSO 前半粒子使用 `target_names` 正序，后半粒子使用反序；奇数迭代轮次整体翻转方向；无上下文时退化为 `target_names` 顺序 |

![image.png](https://raw.gitcode.com/user-images/assets/8473562/b3507c14-72b3-4a70-84a7-09ed17fe0ace/image.png 'image.png')

该修复策略优先保留用户指定或当前粒子策略要求保留的字段，同时在无法保留时仍可通过联合搜索找到自洽组合。

### 数据模型定义

新增或扩展的配置字段如下：

| 字段 | 类型 | 说明 |
| -- | -- | -- |
| `OptimizerConfigField.dtype="ternary_factories"` | 字符串枚举 | 三元除法派生字段，值由两个源字段共同决定 |
| `OptimizerConfigField.dtype="ternary_times"` | 字符串枚举 | 三元乘法派生字段，值由两个源字段共同决定 |
| `dtype_param.target_names` | `list[str]` | 两个依赖字段名称，必须能匹配同一 `target_field` 中的字段名 |
| `dtype_param.product` | `int`/`float` | 乘积系数；缺省为 `1` |
| `dtype_param.dtype` | `str` | 派生结果类型，支持复用 `dtype_func` 中的转换函数 |
| `dtype_param.min_value` | `int`/`float` | `ternary_factories` 结果下界；`int` 类型缺省为 `1` |
| `dtype_param.max_value` | `int`/`float` | `ternary_factories` 结果上界；缺省不限制 |
| `dtype_param.priority_policy` | `fixed`/`balanced` | 三元除法修复优先级策略；缺省为 `balanced` |
| `dtype_param.priority` | `list[str]` | `fixed` 策略下的显式优先级顺序 |
| `DecodeContext.particle_index` | `int` | 当前 PSO 粒子索引，0-based |
| `DecodeContext.n_particles` | `int` | 当前 PSO 种群大小 |
| `DecodeContext.iteration` | `int` | 当前 PSO 迭代轮次，0-based；`balanced` 策略在奇数迭代轮次翻转优先级方向，避免同一粒子在整个优化过程中长期固定偏向同一修复顺序 |

### 影响范围

涉及代码范围如下：

- `ms_serviceparam_optimizer/ms_serviceparam_optimizer/config/config.py`：扩展字段说明、增加 `DecodeContext`、`resolve_priority`、三元推导与修复逻辑；`register_settings`/`get_settings` 支持 `-c/--config` 动态配置注入。
- `ms_serviceparam_optimizer/ms_serviceparam_optimizer/optimizer/optimizer.py`：新增 `-c/--config` 参数定义；在 PSO 粒子评估前传入 `DecodeContext`，并把修复后的真实位置回写到粒子数组；`plugin_main` 中完成路径解析、TOML 格式验证和配置注入。
- `ms_serviceparam_optimizer/ms_serviceparam_optimizer/optimizer/scheduler.py`：`run` 和 `run_with_request_rate` 接收 `decode_context` 并传递给 `map_param_with_value`。
- `test/ut/python/test_optimizer/config/test_config_config.py`：覆盖三元关系、优先级解析、两阶段修复和上下文集成；新增 `-c/--config` 路径解析、文件验证、优先级合并的单元测试。

功能影响：新增配置能力，不改变现有配置的默认行为。未配置三元类型时，旧流程保持不变。

性能影响：修复过程可能枚举两个源字段候选集。`enum` 使用候选列表，`int` 仅在范围长度不超过 256 时枚举，范围过大时返回不可修复并降级，避免搜索开销失控。

可靠性影响：非法 `target_names`、0 值依赖、NaN、非整除且不可修复等场景都会记录 warning 并保持可控降级，不直接中断寻优流程。

安全影响：本特性不新增外部输入入口、不新增文件写入和网络访问；主要风险来自配置错误，已通过字段名校验、候选集限制和 warning 暴露。

## 使用说明

### 使用入口

用户通过现有自动寻优入口启动：

```bash
# 三元关系功能通过配置文件生效
msserviceprofiler optimizer -e mindie -b ais_bench

# 如需指定自定义配置文件，可使用 -c 参数
msserviceprofiler optimizer -e vllm -b vllm_benchmark -c /data/configs/my_config.toml
```

`-c/--config` 参数说明如下：

| 参数 | 可选/必选 | 默认值 | 说明 |
| -- | -- | -- | -- |
| `-c` 或 `--config` | 可选 | `None` | 自定义配置文件路径（TOML 格式）。支持绝对路径、含目录分隔符的相对路径、纯文件名（在当前工作目录下查找）三种形式。指定文件具有最高配置优先级。不指定时工具按默认路径顺序自动搜索配置文件。 |

### 配置参数说明

`ternary_factories` 示例：

```toml
[[mindie.target_field]]
name = "dp"
config_position = "BackendConfig.ModelDeployConfig.ModelConfig.0.dp"
min = 0
max = 0
dtype = "ternary_factories"
dtype_param = { target_names = ["tp", "pp"], product = 32, dtype = "int", min_value = 1, max_value = 32, priority_policy = "balanced" }
```

`ternary_times` 示例：

```toml
[[mindie.target_field]]
name = "total_tokens"
config_position = "Example.totalTokens"
min = 0
max = 0
dtype = "ternary_times"
dtype_param = { target_names = ["seq_len", "batch"], product = 1, dtype = "int" }
```

参数含义如下：

| 参数 | 可选/必选 | 默认值 | 说明 |
| -- | -- | -- | -- |
| `dtype` | 必选 | 无 | 取 `ternary_factories` 或 `ternary_times` |
| `target_names` | 必选 | 无 | 两个依赖字段名，必须与同一 `target_field` 中的 `name` 一致 |
| `product` | 可选 | `1` | 乘积系数；三元除法中作为被除数，三元乘法中作为乘数 |
| `dtype_param.dtype` | 可选 | `int` | 派生结果类型，复用 `int`、`float` 等转换 |
| `min_value` | 可选 | `int` 类型为 `1`，其他类型为无限制 | 三元除法结果下界 |
| `max_value` | 可选 | 无限制 | 三元除法结果上界 |
| `priority_policy` | 可选 | `balanced` | `fixed` 使用显式优先级；`balanced` 按 PSO 粒子分半切换优先级 |
| `priority` | 可选 | `target_names` | `fixed` 策略下的优先级顺序，必须包含两个 `target_names` |

### 使用约束

- `ternary_factories` 和 `ternary_times` 第一版仅支持两个依赖字段。
- `target_names` 必须指向已定义字段；字段名大小写必须一致。
- `ternary_factories` 的依赖字段值不能为 0，否则跳过计算并保留原值。
- `ternary_times` 的依赖字段值不能为 `None` 或 `NaN`，否则跳过计算并保留原值。
- 约束修复只对可枚举候选集生效：`enum` 字段使用 `dtype_param`，`int` 字段仅在范围长度不超过 256 时枚举。
- 若修复失败，三元除法会根据上下界降级截断；对于 `int` 非整除且无法修复、无法安全截断的场景，会抛出 `ValueError` 向上传播，最终由 `op_func` 捕获并置 `fitness=inf`，使 PSO 自动淘汰该不自洽粒子。
- `balanced` 策略只有在 PSO 路径传入 `DecodeContext` 时才能按粒子分半切换；其他调用路径退化为 `target_names` 顺序。
- `-c/--config` 不支持同时传入多个配置文件；如需合并多份配置，请先手动合并后指定。
- `-c/--config` 指定的文件必须为合法 TOML 格式，格式错误时抛出 `ValueError` 并输出详细错误位置。

### 兼容与迁移

既有配置不需要迁移。已有 `factories` 和 `times` 字段继续按原语义执行。插件如需表达 `tp * pp * dp = product` 这类关系，可将派生字段从自定义处理迁移为 `ternary_factories`，并把派生字段配置为 `min = max = 0`，避免其参与 PSO 维度搜索。

`-c/--config` 参数对旧版本完全向前兼容：不指定时行为与历史版本完全一致；已有环境变量 `MODEL_EVAL_STATE_CONFIG_PATH` 仍然有效，但优先级低于 `-c`。

回滚方式是将三元派生字段恢复为旧的二元字段或插件自定义逻辑；命令行入口和结果文件格式不受影响。

## 测试设计

| 用例名 | 测试类型 | 前置条件 | 操作方式 | 预期结果 |
| -- | -- | -- | -- | -- |
| UT-三元除法基本推导 | 单元测试 | `tp=2`、`pp=4`、`product=16` | 调用 `update_optimizer_value` | `dp=2` |
| UT-三元除法浮点推导 | 单元测试 | `tp=2`、`pp=2`、`product=10.0`、`dtype=float` | 调用 `update_optimizer_value` | 派生值为 `2.5` |
| UT-三元除法依赖为零 | 单元测试 | 任一依赖字段值为 `0` | 调用 `update_optimizer_value` | 派生字段保持原值并记录 warning |
| UT-三元乘法基本推导 | 单元测试 | `seq_len=512`、`batch=4`、`product=1` | 调用 `update_optimizer_value` | `total_tokens=2048` |
| UT-依赖字段缺失 | 单元测试 | `target_names` 中存在拼写错误 | 调用 `update_optimizer_value` | 不崩溃，记录字段缺失 warning |
| UT-fixed 优先级解析 | 单元测试 | `priority_policy=fixed` 且 `priority=["pp","tp"]` | 调用 `resolve_priority` | 返回 `["pp","tp"]` |
| UT-fixed 非法优先级降级 | 单元测试 | `priority` 未覆盖全部 `target_names` | 调用 `resolve_priority` | 退化为 `target_names` 顺序 |
| UT-balanced 前半粒子 | 单元测试 | `particle_index < n_particles / 2` | 调用 `resolve_priority` | 使用 `target_names` 正序 |
| UT-balanced 后半粒子 | 单元测试 | `particle_index >= n_particles / 2` | 调用 `resolve_priority` | 使用 `target_names` 反序 |
| UT-优先级修复保留高优字段 | 单元测试 | `fixed` 策略指定 `tp` 高优先级 | 调用 `_repair_ternary_factories_with_priority` | 优先保持 `tp`，调整 `pp` 并得到自洽 `dp` |
| UT-修复失败降级 | 单元测试 | 候选集无合法组合 | 调用 `_repair_ternary_factories_with_priority` | 返回 `False`，调用方执行降级逻辑 |
| IT-map_param 上下文传递 | 集成测试 | 构造含三元字段的 `target_field` 和 `DecodeContext` | 调用 `map_param_with_value` | 输出字段满足三元关系或安全降级 |
| IT-PSO 粒子位置回写 | 集成测试 | 粒子解码触发三元修复 | 调用 `PSOOptimizer.op_func` | 修复后的 `field_to_param` 结果写回 `x[i]` |
| E2E-自动寻优运行 | 端到端测试 | `config.toml` 或插件配置三元派生字段 | 执行 `msserviceprofiler optimizer` | 服务和 benchmark 接收自洽参数，结果文件正常生成 |
| ABN-大范围 int 字段不可枚举 | 异常测试 | 源字段为 `int` 且范围长度超过 256 | 触发修复 | 不进行大范围枚举，降级处理并记录 warning |
| ABN-int 非整除不可修复 | 异常测试 | `product` 不能被任何候选组合整除 | 触发修复 | 抛出 `ValueError`，`op_func` 捕获后置 `fitness=inf`，不自洽粒子被 PSO 淘汰 |
| UT-config-绝对路径 | 单元测试 | 文件在 `/tmp/cfg.toml` | `args.config = "/tmp/cfg.toml"` | 路径解析为绝对路径，配置加载正常 |
| UT-config-仅文件名 | 单元测试 | CWD 为 `/workspace` | `args.config = "cfg.toml"` | 路径解析为 `/workspace/cfg.toml` |
| UT-config-文件不存在 | 单元测试 | 文件不存在 | `-c /nonexistent/path.toml` | 日志记录 `Custom config file not found` 错误并退出，不抛出异常 |
| UT-config-非法TOML | 单元测试 | 文件存在但内容非法 | `-c /path/to/bad.toml` | 抛出 `ValueError`，消息含 TOML 解析错误详情 |
| UT-config-优先级覆盖 | 单元测试 | 默认 `n_particles=5`，用户文件含 `n_particles=20` | `-c /path/user_cfg.toml` | `get_settings().n_particles == 20` |
| UT-config-未覆盖字段继承 | 单元测试 | 默认有 `iters=10`，用户文件不含 `iters` | `-c /path/user_cfg.toml` | `get_settings().iters == 10` |
| ABN-config-权限不足 | 异常测试 | 文件权限为 000 | `-c /path/no_perm.toml` | 进程退出，错误消息含 `Permission denied` |

建议执行现有相关 UT：

```bash
pytest test/ut/python/test_optimizer/config/test_config_config.py
pytest test/ut/python/test_optimizer/optimizer/test_optimizer_optimizer.py
pytest test/ut/python/test_optimizer/optimizer/test_schedule.py
```

其中 `test_config_config.py` 是本特性的主验证入口，重点覆盖 `TestTernaryRelationship`、`TestResolvePriority`、`TestRepairTernaryFactoriesWithPriority` 和 `TestDecodeContextIntegration`。`test_optimizer_optimizer.py` 与 `test_schedule.py` 用于回归 PSO 与调度器调用链，确认上下文透传和既有寻优流程不被破坏。
