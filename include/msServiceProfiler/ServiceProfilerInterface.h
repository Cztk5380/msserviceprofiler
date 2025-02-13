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

#ifndef MS_SERVER_PROFILER_INTERFACE_H
#define MS_SERVER_PROFILER_INTERFACE_H

#include <string>
#include <vector>
#include <dlfcn.h>

using SpanHandle = uint64_t;

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
                std::cout << "find \"libms_service_profiler.so\"" << std::endl;
                ptrIsEnable_ = (decltype(IsEnable)*)dlsym(handle_, "IsEnable");
                ptrStartSpanWithName_ = (decltype(StartSpanWithName)*)dlsym(handle_, "StartSpanWithName");
                ptrMarkSpanAttr_ = (decltype(MarkSpanAttr)*)dlsym(handle_, "MarkSpanAttr");
                ptrEndSpan_ = (decltype(EndSpan)*)dlsym(handle_, "EndSpan");
                ptrMarkEvent_ = (decltype(MarkEvent)*)dlsym(handle_, "MarkEvent");
                ptrStartServerProfiler_ = (decltype(StartServerProfiler)*)dlsym(handle_, "StartServerProfiler");
                ptrStopServerProfiler_ = (decltype(StopServerProfiler)*)dlsym(handle_, "StopServerProfiler");
            } else {
                std::cout << "not find \"libms_service_profiler.so\"" << std::endl;
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
}  // namespace msServiceProfiler

#endif
