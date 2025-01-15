/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef MS_SERVER_PROFILER_MARKER_H
#define MS_SERVER_PROFILER_MARKER_H

#include <string>
#include <vector>
#include <nlohmann/json.hpp>

using SpanHandle = uint64_t;
using json = nlohmann::json;

#define MS_SERVICE_PROFILER_API __attribute__((visibility("default")))


extern "C" {
MS_SERVICE_PROFILER_API SpanHandle StartSpan();
MS_SERVICE_PROFILER_API void MarkSpanAttr(const char *msg, SpanHandle spanHandle);
MS_SERVICE_PROFILER_API void EndSpan(SpanHandle spanHandle);
MS_SERVICE_PROFILER_API void MarkEvent(const char *msg);
MS_SERVICE_PROFILER_API void StartServerProfiler();
MS_SERVICE_PROFILER_API void StopServerProfiler();
MS_SERVICE_PROFILER_API bool IsEnable(uint32_t level);
}

namespace msServiceProfiler {

    enum Level : uint32_t {
        ERROR = 10,
        INFO = 20,
        DETAILED = 30,
        VERBOSE = 40,
    };

    class ServiceProfilerManager {
    public:
        MS_SERVICE_PROFILER_API static ServiceProfilerManager &GetInstance();

        MS_SERVICE_PROFILER_API inline bool IsEnable(uint32_t level)
        {
            return enable_ && level_ > level;
        }

        MS_SERVICE_PROFILER_API void StartProfiler();

        MS_SERVICE_PROFILER_API void StopProfiler();

    private:
        ServiceProfilerManager();

        json ReadConfig();
        bool ReadEnable(const json &config);
        bool ReadProfPath(const json &config);
        bool ReadLevel(const json &config);
        bool ReadCollectConfig(const json &config);
        bool ReadHostConfig(const json &config);
        bool ReadNpuConfig(const json &config);
        void SetAclProfHostSysConfig();
        void DynamicControl();
        void LaunchThread();
        void ThreadFunction();

    private:
        bool enable_ = false;
        bool started_ = false;
        std::string profPath_;
        uint32_t level_ = Level::DETAILED;
        void *configHandle_;
        int lastUpdate_ = 0;

        bool hostCpuUsage_ = false;
        bool hostMemoryUsage_ = false;
        uint32_t hostFreq_ = 10;
        uint32_t hostFreqMin_ = 1;
        uint32_t hostFreqMax_ = 50;

        bool npuMemoryUsage_ = false;
        uint32_t npuMemoryFreq_ = 1;
        uint32_t npuMemoryFreqMin_ = 1;
        uint32_t npuMemoryFreqMax_ = 50;
        uint32_t npuMemorySleepMilliseconds_ = 1000;
    };
}  // namespace msServiceProfiler

#endif
