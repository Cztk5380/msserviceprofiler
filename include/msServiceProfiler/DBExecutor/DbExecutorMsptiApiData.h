/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#ifndef SERVICE_PROFILER_DB_EXECUTOR_MSPTI_API_H
#define SERVICE_PROFILER_DB_EXECUTOR_MSPTI_API_H

#include <string>
#include <sqlite3.h>
#include <cstdio>

#include "../Log.h"
#include "../ServiceProfilerDbWriter.h"
#include "./DbDefines.h"
#include "mspti/mspti.h"

namespace msServiceProfiler {

template <>
class DbExecutor<MSPTI_API_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(const msptiActivityApi &activity)
        : start(activity.start), end(activity.end), processId(activity.pt.processId), threadId(activity.pt.threadId),
          correlationId(activity.correlationId), name(activity.name)
    {}
    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmtMstx = writer.GetStmt(MSPTI_API_INSERT_STMT);
        if (stmtMstx == nullptr) {
            writer.Execute(sqlCreateKindMstx);
            stmtMstx = writer.InitStmt(MSPTI_API_INSERT_STMT, sqlInsertKindMstx);
            if (stmtMstx == nullptr) {
                return;
            }
        }
        if (db == nullptr) {
            return;
        }
        InsertMstxData(db, stmtMstx);
    };

    bool Cache() override
    {
        return false;
    };

private:
    void InsertMstxData(sqlite3 *db, sqlite3_stmt *stmtApi) const
    {
        // 绑定参数
        int bindIndex = 1;
        sqlite3_bind_text(stmtApi, bindIndex++, name.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtApi, bindIndex++, static_cast<int64_t>(start));
        sqlite3_bind_int64(stmtApi, bindIndex++, static_cast<int64_t>(end));
        sqlite3_bind_int64(stmtApi, bindIndex++, processId);
        sqlite3_bind_int64(stmtApi, bindIndex++, threadId);
        sqlite3_bind_int64(stmtApi, bindIndex++, static_cast<int64_t>(correlationId));

        // 执行插入
        if (sqlite3_step(stmtApi) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtApi);
    }

private:
    uint64_t start;  // API执行的开始时间戳，单位ns。开始和结束时间戳均为0时则无法收集API的时间戳信息
    uint64_t end;  // API执行的结束时间戳，单位ns。开始和结束时间戳均为0时则无法收集API的时间戳信息
    uint32_t processId;      // API运行设备的进程ID
    uint32_t threadId;       // API运行流的线程ID
    uint64_t correlationId;  // API的关联ID。每个API执行都被分配一个唯一的关联ID，该关联ID与启动API的驱动程序或运行时API
                             // Activity Record的关联ID相同
    std::string name;
    const char *sqlCreateKindMstx = "CREATE TABLE IF NOT EXISTS Api ("
                                    "name TEXT,"
                                    "start INTEGER,"
                                    "end INTEGER,"
                                    "processId INTEGER,"
                                    "threadId INTEGER,"
                                    "correlationId INTEGER);";
    const char *sqlInsertKindMstx = "INSERT INTO Api "
                                    "(name, start, end, processId, threadId, correlationId) "
                                    "VALUES (?, ?, ?, ?, ?, ?);";
};

}  // namespace msServiceProfiler

#endif  // SERVICE_PROFILER_DB_EXECUTOR_MSPTI_API_H
