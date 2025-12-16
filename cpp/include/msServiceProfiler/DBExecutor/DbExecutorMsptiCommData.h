/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#ifndef SERVICE_PROFILER_DB_EXECUTOR_MSPTI_COMM_H
#define SERVICE_PROFILER_DB_EXECUTOR_MSPTI_COMM_H

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
class DbExecutor<MSPTI_COMMUNICATION_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(const msptiActivityCommunication &activity)
        : dataType(activity.dataType), count(activity.count), deviceId(activity.ds.deviceId),
          streamId(activity.ds.streamId), start(activity.start), end(activity.end), name(activity.name),
          commName(activity.commName), correlationId(activity.correlationId)
    {}
    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmtMstx = writer.GetStmt(MSPTI_COMMUNICATION_INSERT_STMT);
        if (stmtMstx == nullptr) {
            writer.Execute(sqlCreateKindMstx);
            stmtMstx = writer.InitStmt(MSPTI_COMMUNICATION_INSERT_STMT, sqlInsertKindMstx);
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
    void InsertMstxData(sqlite3 *db, sqlite3_stmt *stmtCommunication) const
    {
        // 绑定参数
        int bindIndex = 1;
        sqlite3_bind_text(stmtCommunication, bindIndex++, name.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(start));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(end));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(deviceId));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(streamId));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(count));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(dataType));
        sqlite3_bind_text(stmtCommunication, bindIndex++, commName.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(correlationId));

        // 执行插入
        if (sqlite3_step(stmtCommunication) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtCommunication);
    }

private:
    msptiCommunicationDataType dataType;  // 通信算子数据类型
    uint64_t count;                       // 通信数据量
    uint32_t deviceId;                    // 通信算子运行设备的Device ID
    uint32_t streamId;                    // 通信算子运行流的Stream ID
    uint64_t start;  // 通信算子在NPU设备上执行开始时间戳，单位ns。开始和结束时间戳均为0时则无法收集通信算子的时间戳信息
    uint64_t end;  // 通信算子执行的结束时间戳，单位ns。开始和结束时间戳均为0时则无法收集通信算子的时间戳信息
    std::string name;      // 通信算子的名称
    std::string commName;  // 通信算子所在通信域的名称
    uint64_t correlationId;
    const char *sqlCreateKindMstx = "CREATE TABLE IF NOT EXISTS Communication ("
                                    "name TEXT,"
                                    "start INTEGER,"
                                    "end INTEGER,"
                                    "deviceId INTEGER,"
                                    "streamId INTEGER,"
                                    "dataCount INTEGER,"
                                    "dataType INTEGER,"
                                    "commGroupName TEXT,"
                                    "correlationId INTEGER);";
    const char *sqlInsertKindMstx =
        "INSERT INTO Communication "
        "(name, start, end, deviceId, streamId, dataCount, dataType, commGroupName, correlationId) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);";
};

}  // namespace msServiceProfiler

#endif  // SERVICE_PROFILER_DB_EXECUTOR_MSPTI_COMM_H
