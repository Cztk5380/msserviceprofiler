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

namespace {
    constexpr int ALIGN_SIZE = 8;
    constexpr int ONE_K = 1024;
    const char SPLIT_SYMBOL = ';';
} // end of anonymous namespace

namespace msServiceProfiler {
int InitMspti(std::string& profPath_, msptiSubscriberHandle& subscriber);
void InitMsptiActivity(bool msptiEnable_);
void InitMsptiFilter(std::string& apiFilter, std::string& kernelFilter);
void UninitMspti(msptiSubscriberHandle& subscriber);
void FlushBufferByTime();

class ServiceProfilerMspti {
public:
    static ServiceProfilerMspti &GetInstance()
    {
        static ServiceProfilerMspti manager;
        return manager;
    };

    void insertApiData(msptiActivityApi* activity);

    void insertKernelData(msptiActivityKernel* activity);

    void insertCommData(msptiActivityHccl* activity);

    void insertMstxData(msptiActivityMarker* activity);

    void Init();

    void InitFilter(std::string& apiFilter, std::string& kernelFilter);

    void InitOutputPath(std::string& outputPath);

    void Close();

    void AddWorkingThreadNum();

    void PopWorkingThreadNum();

    void ResetWorkingThreadNum();

    bool GetWorkingStatus();

private:

    void createTable();

    void createMstxTable();

    void createApiTable();

    void createKernelTable();

    void createCommTable();

private:
    static constexpr size_t buffer_size = 5 * ONE_K * ONE_K;
    char buffer[buffer_size];
    bool inited = false;
    int workingThreadNum = 0;
    std::string file_name;
    sqlite3* db;
    sqlite3_stmt* stmtApi;
    sqlite3_stmt* stmtKernel;
    sqlite3_stmt* stmtComm;
    sqlite3_stmt* stmtMstx;
    std::set<std::string> filterApi;
    std::set<std::string> filterKernel;
};
}
#endif // SERVICEPROFILERMANAGERMSPTI_H
