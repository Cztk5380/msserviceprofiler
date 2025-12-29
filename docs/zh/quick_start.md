# 服务化调优<a name="ZH-CN_TOPIC_0000002475358702"></a>

服务化框架的性能调优往往如同置身 “黑盒”，问题根源难以精准定位 —— 比如请求量攀升后响应速度显著下降、硬件设备更换后性能表现迥异等场景，都难以快速排查。

msServiceProfiler（服务化调优工具）提供全链路性能剖析，清晰展示框架调度、模型推理等环节的表现，帮助用户快速找到性能瓶颈（帮助判断是框架问题还是模型问题），从而有效提升服务性能。

>![](public_sys-resources/icon-note.gif) **说明：** 
>以下仅提供服务化调优工具的快速入门，工具更多操作及接口、参数、字段等详细内容介绍请参见“服务化调优工具”。

## 前提条件<a name="section1605203618349"></a>

-   在使用性能调优工具前，请先阅读《msServiceProfiler工具安装指南》中的“[约束](msserviceprofiler_install_guide.md#约束)”章节的使用约束，了解相关约束条件。
-   请参见《MindIE安装指南》完成MindIE的安装和配置并确认MindIE Motor可以正常运行。

## 操作步骤<a name="section166491954201410"></a>

1.  <a name="li104932444507"></a>配置环境变量。

    msServiceProfiler的采集能力需要在部署MindIE Motor服务之前，通过设置环境变量SERVICE\_PROF\_CONFIG\_PATH方能生效。如果环境变量拼写错误，或者没有在部署MindIE Motor服务之前设置环境变量，都无法使能msServiceProfiler的采集能力。

    以ms\_service\_profiler\_config.json文件名为例，执行下列命令配置环境变量。

    ```
    export SERVICE_PROF_CONFIG_PATH="./ms_service_profiler_config.json"
    ```

    SERVICE\_PROF\_CONFIG\_PATH的值需要指定到json文件名，该json文件即为控制性能数据采集的配置文件，比如采集性能元数据存放位置、算子采集开关等，具体字段介绍参考[数据采集](#li10670349115211)。若路径下无配置文件，工具将自动生成默认配置（采集开关默认为关闭状态）。

    >![](public_sys-resources/icon-caution.gif) **注意：** 
    >在多机部署时，通常不建议将配置文件或其指定的数据存储路径放置在共享目录（如网络共享位置）。 由于数据写入方式可能涉及额外的网络或缓冲环节，而非直接落盘，此类配置在某些情况下可能导致预期外的系统行为或结果。

2.  运行MindIE Motor服务。

    如果正确配置了环境变量，工具会在服务部署完成之前输出如下\[msservice\_profiler\]开头的日志，说明msServiceProfiler已启动，如下所示。

    ```
    [msservice_profiler] [PID:225] [INFO] [ParseEnable:179] profile enable_: false
    [msservice_profiler] [PID:225] [INFO] [ParseAclTaskTime:264] profile enableAclTaskTime_: false
    [msservice_profiler] [PID:225] [INFO] [ParseAclTaskTime:265] profile msptiEnable_: false
    [msservice_profiler] [PID:225] [INFO] [LogDomainInfo:357] profile enableDomainFilter_: false
    ```

    如果SERVICE\_PROF\_CONFIG\_PATH环境变量所指定的配置文件不存在，工具输出自动创建的日志。以[1](#li104932444507)的配置为例，那么工具输出日志如下。

    ```
    [msservice_profiler] [PID:225] [INFO] [SaveConfigToJsonFile:588] Successfully saved profiler configuration to: ./ms_service_profiler_config.json
    ```

3. <a name="li10670349115211"></a>数据采集。

   MindIE Motor服务部署成功之后，可以通过修改配置文件中的字段来进行精准控制采集行为（此处仅以配置以下三个字段为例）。

   ```
   {
   	"enable": 1,
   	"prof_dir": "${PATH}/prof_dir/",
   	"acl_task_time": 0
   }
   ```

   **表 1**  参数说明

   | 参数          | 说明                                                         | 是否必选 |
   | ------------- | ------------------------------------------------------------ | -------- |
   | enable        | 性能数据采集总开关。取值为：<br>0：关闭。<br/>1：开启。<br/>即便其他开关开启，该开关不开启，仍然不会进行任何数据采集；如果只有该开关开启，只采集服务化性能数据。 | 是       |
   | prof_dir      | 采集到的性能数据的存放路径，默认值为${HOME}/.ms_server_profiler。<br/>该路径下存放的是性能原始数据，需要继续执行后续解析步骤，才能获取可视化的性能数据文件进行分析。<br/>在enable为0时，对prof_dir进行自定义修改，随后修改enable为1时生效；在enable为1时，直接修改prof_dir，则修改不生效。 | 否       |
   | acl_task_time | 开启采集算子下发耗时、算子执行耗时数据的开关，取值为<br/>：0：关闭。默认值，配置为0或其他非法值均表示关闭。<br/>1：开启。<br/>该功能开启时会占用一定的设备性能，导致采集的性能数据不准确，建议在模型执行耗时异常时开启，用于更细致的分析。<br/>算子采集数据量较大，一般推荐集中采集3 ~ 5s，时间过长会导致占用额外磁盘空间，消耗额外的解析时间，从而导致性能定位时间拉长。<br/>默认算子采集等级为L0，如果需要开启其他算子采集等级，请参见“服务化调优工具”的完整参数介绍。 | 否       |

   一般来说，如果enable一直为1，当MindIE Motor推理服务从收到请求的那一刻，工具会一直采集，直到请求结束，prof\_dir下的目录大小也会不断增长，因此推荐用户仅采集关键时间段的信息。

   每当enable字段发生变更时，工具都会输出对应的日志进行告知。

   ```
   [msservice_profiler] [PID:3259] [INFO] [DynamicControl:407] Profiler Enabled Successfully!
   ```
   或者
   ```
   [msservice_profiler] [PID:3057] [INFO] [DynamicControl:411] Profiler Disabled Successfully!
   ```

   每当enable由0改为1时，配置文件中的所有字段都会被工具重新加载，从而实现动态地更新。

4. 数据解析。

   1.  安装环境依赖。

       ```
       python >= 3.10
       pandas >= 2.2
       numpy >= 1.24.3
       psutil >= 5.9.5
       ```

   2.  执行解析命令示例：

       ```
       python3 -m ms_service_profiler.parse --input-path=${PATH}/prof_dir
       ```

       --input-path指定为[数据采集](#li10670349115211)中**prof\_dir**参数指定的路径。

       解析完成后默认在命令执行目录下生成解析后的性能数据文件。

5. 调优分析。

   解析后的性能数据包含db格式、csv格式和json格式，用户可以通过csv进行请求、调度等不同维度的快速分析，也可以通过MindStudio Insight工具导入db文件或者json文件进行可视化分析，详细操作和分析说明请参见《MindStudio Insight工具用户指南》中的“服务化调优”章节。

   根据MindStudio Insight工具的可视化呈现性能数据，如下图所示：

   ![](figures/zh-cn_image_0000002478067012.png)

