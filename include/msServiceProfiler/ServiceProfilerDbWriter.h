/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
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

#ifndef SERVICEPROFILERDBWRITER_H
#define SERVICEPROFILERDBWRITER_H

#include <cstdint>
#include <string>
#include <mutex>
#include <map>
#include <set>
#include <vector>
#include <memory>
#include <thread>
#include <sqlite3.h>

namespace msServiceProfiler {

enum class ActivityFlag {
    ACTIVITY_FLAG_MARKER_EVENT = 1,
    ACTIVITY_FLAG_MARKER_SPAN = 2,
};


// 定义 DbActivityMarker
using DbActivityMarker = struct PACKED_ALIGNMENT_DB {
    ActivityFlag flag;
    uint64_t timestamp;
    uint64_t endTimestamp;
    uint64_t id;
    uint32_t processId;
    uint32_t threadId;
    std::string message;
};

class ServiceProfilerThreadWriter;
class DbBuffer;

class ServiceProfilerDbWriter {
public:
    static ServiceProfilerDbWriter &GetInstance();

    void InsertMstxData(DbActivityMarker *activity) const;
    void Flash() const;
    void InsertMetaData(const std::string &name, const std::string &value) const;
    void Init(const std::string &outputPath);
    void CreateTable();
    void ApplyOptimizations() const;
    void Close();

private:
    ServiceProfilerDbWriter();
    ~ServiceProfilerDbWriter();

    void Execute(const char *sql) const;

    bool inited = false;
    sqlite3 *db_ = nullptr;
    sqlite3_stmt *stmtMstx_ = nullptr;
    sqlite3_stmt *stmtMeta_ = nullptr;
};

class ServiceProfilerWriterManager {
public:
    static ServiceProfilerWriterManager &GetInstance();

    DbBuffer *Register(ServiceProfilerThreadWriter *pThreadIns);
    void Unregister(ServiceProfilerThreadWriter *pThreadIns);
    void Start(const std::string &outputPath);
    void Close();

private:
    ServiceProfilerWriterManager();
    ~ServiceProfilerWriterManager();

    void ThreadFunction();
    int PopAndInsert2DB(std::vector<DbBuffer *> &workingDbBuffers, std::set<DbBuffer *> &disableDbBuffers,
                        std::vector<DbBuffer *> &freeDbBuffers);

    std::mutex mtx_;
    std::map<ServiceProfilerThreadWriter *, DbBuffer *> mapBuffer_;
    std::thread thread_;
    std::set<DbBuffer *> disableDbBuffers_;
    std::vector<DbBuffer *> workingDbBuffers_;
    bool closeFlag_ = false;
    bool threadExitFlag_ = false;
    std::string profPath_;
};

class ServiceProfilerThreadWriter {
public:
    ServiceProfilerThreadWriter();
    ~ServiceProfilerThreadWriter();
    void Insert(DbActivityMarker *activity);

private:
    DbBuffer *pBuffer = nullptr;
};

void InsertTxData2Writer(DbActivityMarker *activity);
void CloseTxData2Writer();
void StartTxData2Writer(const std::string &outputPath);
std::string GetHostName();
uint32_t GetTid();

}  // namespace msServiceProfiler

#endif  // SERVICEPROFILERDBWRITER_H