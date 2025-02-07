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
#include <dlfcn.h>
#include <nlohmann/json.hpp>

using SpanHandle = uint64_t;
using json = nlohmann::json;

#define MS_SERVICE_PROFILER_API __attribute__((visibility("default")))


extern "C" {
MS_SERVICE_PROFILER_API SpanHandle StartSpan();
MS_SERVICE_PROFILER_API SpanHandle StartSpanWithName(const char *name);
MS_SERVICE_PROFILER_API void MarkSpanAttr(const char *msg, SpanHandle spanHandle);
MS_SERVICE_PROFILER_API void EndSpan(SpanHandle spanHandle);
MS_SERVICE_PROFILER_API void MarkEvent(const char *msg);
MS_SERVICE_PROFILER_API void StartServerProfiler();
MS_SERVICE_PROFILER_API void StopServerProfiler();
MS_SERVICE_PROFILER_API bool IsEnable(uint32_t level);
}

namespace msServiceProfilerCompatible {
    class ProfilerFunc {
    public:
        static ProfilerFunc &GetInstance()
        {
            static ProfilerFunc logManager;
            return logManager;
        }

        ~ProfilerFunc() = default;

        inline SpanHandle CallStartSpanWithName(const char *name)
        {
            return ptrStartSpanWithName_ ? ptrStartSpanWithName_(name) : 0;
        }

        inline void CallMarkSpanAttr(const char *msg, SpanHandle spanHandle)
        {
            if (ptrMarkSpanAttr_) {
                ptrMarkSpanAttr_(msg, spanHandle);
            }
        }

        inline void CallEndSpan(SpanHandle spanHandle)
        {
            if (ptrEndSpan_) {
                ptrEndSpan_(spanHandle);
            }
        }

        inline void CallMarkEvent(const char *msg)
        {
            if (ptrMarkEvent_) {
                ptrMarkEvent_(msg);
            }
        }

        inline bool CallIsEnable(uint32_t level)
        {
            return ptrIsEnable_ && ptrIsEnable_(level);
        }

        inline void CallStartServerProfiler()
        {
            if (ptrStartServerProfiler_) {
                ptrStartServerProfiler_();
            }
        }

        inline void CallStopServerProfiler()
        {
            if (ptrStopServerProfiler_) {
                ptrStopServerProfiler_();
            }
        }

    private:
        void *handle_ = nullptr;
        decltype(IsEnable)* ptrIsEnable_ = nullptr;
        decltype(StartSpanWithName)* ptrStartSpanWithName_ = nullptr;
        decltype(MarkSpanAttr)* ptrMarkSpanAttr_ = nullptr;
        decltype(EndSpan)* ptrEndSpan_ = nullptr;
        decltype(MarkEvent)* ptrMarkEvent_ = nullptr;
        decltype(StartServerProfiler)* ptrStartServerProfiler_ = nullptr;
        decltype(StopServerProfiler)* ptrStopServerProfiler_ = nullptr;
    private:
        ProfilerFunc()
        {
            handle_ = dlopen("libms_service_profiler.so", RTLD_LAZY);
            if (handle_) {
                ptrIsEnable_ = (decltype(IsEnable)*)dlsym(handle_, "IsEnable");
                ptrStartSpanWithName_ = (decltype(StartSpanWithName)*)dlsym(handle_, "StartSpanWithName");
                ptrMarkSpanAttr_ = (decltype(MarkSpanAttr)*)dlsym(handle_, "MarkSpanAttr");
                ptrEndSpan_ = (decltype(EndSpan)*)dlsym(handle_, "EndSpan");
                ptrMarkEvent_ = (decltype(MarkEvent)*)dlsym(handle_, "MarkEvent");
                ptrStartServerProfiler_ = (decltype(StartServerProfiler)*)dlsym(handle_, "StartServerProfiler");
                ptrStopServerProfiler_ = (decltype(StopServerProfiler)*)dlsym(handle_, "StopServerProfiler");
            }
        };

        ProfilerFunc(const ProfilerFunc &) = delete;

        ProfilerFunc &operator=(const ProfilerFunc &) = delete;

        ProfilerFunc(ProfilerFunc &&) = delete;

        ProfilerFunc &operator=(ProfilerFunc &&) = delete;
    };
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
        static ServiceProfilerManager &GetInstance();

        inline bool IsEnable(uint32_t level)
        {
            return enable_ && level_ >= level;
        }

        void StartProfiler();

        void StopProfiler();

        static std::string ToSemName(const std::string &oriSemName);

        std::string &GetConfigPath()
        {
            return configPath_;
        }

    private:
        ServiceProfilerManager();

        ~ServiceProfilerManager();

        json ReadConfig();

        void ReadEnable(const json &config);

        void ReadProfPath(const json &config);

        void ReadLevel(const json &config);

        void ReadAclTaskTime(const json &config);

        bool ReadCollectConfig(const json &config);

        bool ReadHostConfig(const json &config);

        bool ReadNpuConfig(const json &config);

        void SetAclProfHostSysConfig();

        void DynamicControl();

        void LaunchThread();

        void ThreadFunction();

        void ReadConfigPath();

        void MarkFirstProcessAsMain();

        void InitProfPathDateTail(bool forceReinit = false);

    private:
        bool isMaster_ = true;
        bool enable_ = false;
        bool started_ = false;
        std::string configPath_;
        std::string profPath_;
        std::string profPathDateTail_;
        uint32_t level_ = Level::INFO;
        bool enableAclTaskTime_ = false;
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
