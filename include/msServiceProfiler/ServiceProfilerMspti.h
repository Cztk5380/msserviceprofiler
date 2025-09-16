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

#ifndef SERVICEPROFILERMANAGERMSPTI_H
#define SERVICEPROFILERMANAGERMSPTI_H

#include <set>
#include <string>
#include <sqlite3.h>

#include "mspti/mspti.h"

namespace msServiceProfiler {
constexpr int ALIGN_SIZE = 8;
constexpr int ONE_K = 1024;
const char SPLIT_SYMBOL = ';';
int InitMspti(const std::string &profPath_, msptiSubscriberHandle &subscriber);
void InitMsptiActivity(bool msptiEnable);
void InitMsptiFilter(const std::string &apiFilter, const std::string &kernelFilter);
void UninitMspti(msptiSubscriberHandle &subscriber);
void FlushBufferByTime();

class ServiceProfilerMspti {
public:
    ServiceProfilerMspti(const ServiceProfilerMspti &) = delete;

    ServiceProfilerMspti &operator=(const ServiceProfilerMspti &) = delete;

    ServiceProfilerMspti(ServiceProfilerMspti &&) = delete;

    ServiceProfilerMspti &operator=(ServiceProfilerMspti &&) = delete;

    static ServiceProfilerMspti &GetInstance()
    {
        static ServiceProfilerMspti manager;
        return manager;
    };

    void Init();

    void InitFilter(const std::string &apiFilter, const std::string &kernelFilter);

    bool ApiNameMatch(const char *name) const
    {
        return IsNameMatch(filterApi, name);
    }
    bool KernelNameMatch(const char *name) const
    {
        return IsNameMatch(filterKernel, name);
    }

    void InitOutputPath(const std::string &outputPath);

    void Close();

    void AddWorkingThreadNum();

    void PopWorkingThreadNum();

    void ResetWorkingThreadNum();

    bool GetWorkingStatus() const;

private:
    ServiceProfilerMspti() = default;

    static bool IsNameMatch(const std::set<std::string> &filterSet, const char *name);

private:
    static constexpr size_t buffer_size = 5 * ONE_K * ONE_K;
    char buffer[buffer_size];
    bool inited = false;
    int workingThreadNum = 0;
    std::string outputDir_;
    sqlite3 *db;
    sqlite3_stmt *stmtApi;
    sqlite3_stmt *stmtKernel;
    sqlite3_stmt *stmtCommunication;
    sqlite3_stmt *stmtMstx;
    std::set<std::string> filterApi;
    std::set<std::string> filterKernel;
};
}  // namespace msServiceProfiler
#endif  // SERVICEPROFILERMANAGERMSPTI_H
