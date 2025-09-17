/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#ifndef SERVICE_PROFILER_DB_EXECUTOR_MSTX_H
#define SERVICE_PROFILER_DB_EXECUTOR_MSTX_H

#include <cstdint>
#include <string>
#include <sqlite3.h>
#include <cstdio>

#include "../Log.h"
#include "../ServiceProfilerDbWriter.h"
#include "./DbDefines.h"

namespace msServiceProfiler {

enum class ActivityFlag {
    ACTIVITY_FLAG_MARKER_EVENT = 1,
    ACTIVITY_FLAG_MARKER_SPAN = 2,
};

using DbActivityMarker = struct PACKED_MARKER_DB {
    ActivityFlag flag;
    uint64_t timestamp;
    uint64_t endTimestamp;
    uint64_t id;
    uint32_t processId;
    uint32_t threadId;
    std::string message;
};

template <>
class DbExecutor<SERVICE_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(DbActivityMarker &&mstxData) : activity(std::move(mstxData))
    {}
    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmtMstx = writer.GetStmt(SERVICE_INSERT_STMT);
        if (stmtMstx == nullptr) {
            writer.Execute(sqlCreateKindMstx);
            stmtMstx = writer.InitStmt(SERVICE_INSERT_STMT, sqlInsertKindMstx);
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
    void InsertMstxData(sqlite3 *db, sqlite3_stmt *stmtMstx) const
    {
        // 绑定参数
        int bindIndex = 0;
        if (sqlite3_bind_text(stmtMstx, ++bindIndex, activity.message.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            sqlite3_reset(stmtMstx);
            return;
        }
        if (sqlite3_bind_int64(stmtMstx, ++bindIndex, static_cast<int64_t>(activity.flag)) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            sqlite3_reset(stmtMstx);
            return;
        }
        if (sqlite3_bind_int64(stmtMstx, ++bindIndex, static_cast<int64_t>(activity.id)) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            sqlite3_reset(stmtMstx);
            return;
        }
        if (sqlite3_bind_int64(stmtMstx, ++bindIndex, static_cast<int64_t>(activity.timestamp)) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            sqlite3_reset(stmtMstx);
            return;
        }
        if (sqlite3_bind_int64(stmtMstx, ++bindIndex, static_cast<int64_t>(activity.endTimestamp)) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            sqlite3_reset(stmtMstx);
            return;
        }
        if (sqlite3_bind_int64(stmtMstx, ++bindIndex, activity.processId) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            sqlite3_reset(stmtMstx);
            return;
        }
        if (sqlite3_bind_int64(stmtMstx, ++bindIndex, activity.threadId) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            sqlite3_reset(stmtMstx);
            return;
        }

        // 执行插入
        if (sqlite3_step(stmtMstx) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtMstx);
    }

private:
    DbActivityMarker activity;
    const char *sqlCreateKindMstx = "CREATE TABLE IF NOT EXISTS Mstx ("
                                    "message TEXT,"
                                    "flag INTEGER,"
                                    "markId INTEGER,"
                                    "timestamp INTEGER,"
                                    "endTimestamp INTEGER,"
                                    "pid INTEGER,"
                                    "tid INTEGER);";
    const char *sqlInsertKindMstx = "INSERT INTO Mstx "
                                    "(message, flag, markId, timestamp, endTimestamp, pid, tid) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?);";
};

}  // namespace msServiceProfiler

#endif  // SERVICE_PROFILER_DB_EXECUTOR_MSTX_H
