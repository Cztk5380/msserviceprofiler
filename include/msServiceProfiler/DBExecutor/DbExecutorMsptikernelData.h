/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#ifndef SERVICE_PROFILER_DB_EXECUTOR_MSPTI_KERNEL_H
#define SERVICE_PROFILER_DB_EXECUTOR_MSPTI_KERNEL_H

#include <cstdint>
#include <string>
#include <sqlite3.h>
#include <cstdio>

#include "../Log.h"
#include "../ServiceProfilerDbWriter.h"
#include "./DbDefines.h"
#include "mspti/mspti.h"

namespace msServiceProfiler {

template <>
class DbExecutor<MSPTI_KERNEL_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(const msptiActivityKernel &activity)
        : start(activity.start), end(activity.end), deviceId(activity.ds.deviceId), streamId(activity.ds.streamId),
          correlationId(activity.correlationId), name(activity.name), type(activity.type)
    {}
    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmtMstx = writer.GetStmt(MSPTI_KERNEL_INSERT_STMT);
        if (stmtMstx == nullptr) {
            writer.Execute(sqlCreateKindMstx);
            stmtMstx = writer.InitStmt(MSPTI_KERNEL_INSERT_STMT, sqlInsertKindMstx);
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
    void InsertMstxData(sqlite3 *db, sqlite3_stmt *stmtKernel) const
    {
        // 绑定参数
        int bindIndex = 1;
        sqlite3_bind_text(stmtKernel, bindIndex++, type.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmtKernel, bindIndex++, name.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtKernel, bindIndex++, static_cast<int64_t>(start));
        sqlite3_bind_int64(stmtKernel, bindIndex++, static_cast<int64_t>(end));
        sqlite3_bind_int64(stmtKernel, bindIndex++, deviceId);
        sqlite3_bind_int64(stmtKernel, bindIndex++, streamId);
        sqlite3_bind_int64(stmtKernel, bindIndex++, static_cast<int64_t>(correlationId));

        // 执行插入
        if (sqlite3_step(stmtKernel) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtKernel);
    }

private:
    uint64_t start;  // Kernel在NPU设备上执行开始时间戳，单位ns。开始和结束时间戳均为0时则无法收集kernel的时间戳信息
    uint64_t end;  // kernel执行的结束时间戳，单位ns。开始和结束时间戳均为0时则无法收集kernel的时间戳信息
    uint32_t deviceId;  // kernel运行设备的Device ID
    uint32_t streamId;  // kernel运行流的Stream ID
    uint64_t correlationId;  // Runtime在Launch Kernel时生成的唯一ID，其它Activity可通过该值与Kernel进行关联
    std::string name;
    std::string type;
    const char *sqlCreateKindMstx = "CREATE TABLE IF NOT EXISTS Kernel ("
                                    "type TEXT,"
                                    "name TEXT,"
                                    "start INTEGER,"
                                    "end INTEGER,"
                                    "deviceId INTEGER,"
                                    "streamId INTEGER,"
                                    "correlationId INTEGER);";
    const char *sqlInsertKindMstx = "INSERT INTO Kernel "
                                    "(type, name, start, end, deviceId, streamId, correlationId) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?);";
};

}  // namespace msServiceProfiler

#endif  // SERVICE_PROFILER_DB_EXECUTOR_MSPTI_KERNEL_H
