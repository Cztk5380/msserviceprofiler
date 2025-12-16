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

#ifndef SERVICE_PROFILER_DB_EXECUTOR_MSPTI_MSTX_H
#define SERVICE_PROFILER_DB_EXECUTOR_MSPTI_MSTX_H

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
class DbExecutor<MSPTI_MSTX_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(const msptiActivityMarker &activity)
        : kind(activity.kind), flag(activity.flag), sourceKind(activity.sourceKind), timestamp(activity.timestamp),
          id(activity.id), objectId(activity.objectId), name(activity.name)
    {}
    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmtMstx = writer.GetStmt(MSPTI_MSTX_INSERT_STMT);
        if (stmtMstx == nullptr) {
            writer.Execute(sqlCreateKindMstx);
            stmtMstx = writer.InitStmt(MSPTI_MSTX_INSERT_STMT, sqlInsertKindMstx);
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
        int bindIndex = 1;
        if (sourceKind == MSPTI_ACTIVITY_SOURCE_KIND_HOST) {
            sqlite3_bind_int64(stmtMstx, bindIndex++, objectId.pt.processId);
            sqlite3_bind_int64(stmtMstx, bindIndex++, objectId.pt.threadId);
        } else {
            sqlite3_bind_int64(stmtMstx, bindIndex++, -1);
            sqlite3_bind_int64(stmtMstx, bindIndex++, -1);
        }
        sqlite3_bind_int64(stmtMstx, bindIndex++, flag);
        sqlite3_bind_int64(stmtMstx, bindIndex++, static_cast<int64_t>(timestamp));

        sqlite3_bind_int64(stmtMstx, bindIndex++, static_cast<int64_t>(id));
        sqlite3_bind_int64(stmtMstx, bindIndex++, sourceKind);
        sqlite3_bind_text(stmtMstx, bindIndex++, name.c_str(), -1, SQLITE_STATIC);

        // 执行插入
        if (sqlite3_step(stmtMstx) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtMstx);
    }

private:
    msptiActivityKind kind;
    msptiActivityFlag flag;
    msptiActivitySourceKind sourceKind;
    uint64_t timestamp;
    uint64_t id;
    msptiObjectId objectId;
    std::string name;
    const char *sqlCreateKindMstx = "CREATE TABLE IF NOT EXISTS Mstx ("
                                    "pid INTEGER,"
                                    "tid INTEGER,"
                                    "event_type TEXT,"
                                    "timestamp INTEGER,"
                                    "mark_id INTEGER,"
                                    "domain TEXT,"
                                    "message TEXT);";
    const char *sqlInsertKindMstx = "INSERT INTO Mstx "
                                    "(pid, tid, event_type, timestamp, mark_id, domain, message) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?);";
};

}  // namespace msServiceProfiler

#endif  // SERVICE_PROFILER_DB_EXECUTOR_MSPTI_MSTX_H
