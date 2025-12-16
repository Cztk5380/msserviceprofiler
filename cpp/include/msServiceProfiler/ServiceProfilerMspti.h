/* -------------------------------------------------------------------------
 * This file is part of the MindStudio project.
 * Copyright (c) 2025 Huawei Technologies Co.,Ltd.
 *
 * MindStudio is licensed under Mulan PSL v2.
 * You can use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *
 *          http://license.coscl.org.cn/MulanPSL2
 *
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
 * EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
 * MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
 * See the Mulan PSL v2 for more details.
 * -------------------------------------------------------------------------
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
