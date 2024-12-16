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

using SpanHandle = uint64_t;

extern "C" {
SpanHandle StartSpan();
void MarkSpanAttr(const char *msg, SpanHandle spanHandle);
void EndSpan(SpanHandle spanHandle);
void MarkEvent(const char *msg);
void StartServerProfiler();
void StopServerProfiler();
bool IsEnable(uint32_t level);
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
            return enable_ && level_ > level;
        }

        void StartProfiler();

        void StopProfiler();

    private:
        ServiceProfilerManager();

        void ReadConfig();

        bool ReadEnable(const std::string &key, const std::string &value);

        bool ReadProfPath(const std::string &key, const std::string &value);

        bool ReadLevel(const std::string &key, const std::string &value);

    private:
        bool enable_ = false;
        bool started_ = false;
        std::string profPath_;
        uint32_t level_ = Level::DETAILED;
        void *configHandle_;
    };
}  // namespace msServiceProfiler

#endif