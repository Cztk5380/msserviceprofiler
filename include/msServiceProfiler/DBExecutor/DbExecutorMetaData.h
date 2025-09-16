/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#ifndef SERVICE_PROFILER_DB_EXECUTOR_META_H
#define SERVICE_PROFILER_DB_EXECUTOR_META_H

#include <cstdint>
#include <string>
#include <fstream>
#include <utility>
#include "../ServiceProfilerDbWriter.h"
#include "./DbDefines.h"
#include "../Log.h"

namespace msServiceProfiler {

template <>
class DbExecutor<META_INSERT_STMT> : public DbExecutorInterface {
public:
    DbExecutor(std::string metaKey, std::string metaValue)
        : metaKey_(std::move(metaKey)), metaValue_(std::move(metaValue))
    {}
    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmtMeta = writer.GetStmt(META_INSERT_STMT);
        if (stmtMeta == nullptr) {
            writer.Execute(sqlCreateKindMeta);
            stmtMeta = writer.InitStmt(META_INSERT_STMT, sqlInsertKindMeta);
            if (stmtMeta == nullptr) {
                return;
            }
        }
        if (db == nullptr) {
            return;
        }
        InsertMetaData(db, stmtMeta);
    };

    bool Cache() override
    {
        return true;
    };

private:
    void InsertMetaData(sqlite3 *db, sqlite3_stmt *stmtMeta) const
    {
        // 绑定参数
        int bindIndex = 0;
        if (sqlite3_bind_text(stmtMeta, ++bindIndex, metaKey_.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            sqlite3_reset(stmtMeta);
            return;
        }
        if (sqlite3_bind_text(stmtMeta, ++bindIndex, metaValue_.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            sqlite3_reset(stmtMeta);
            return;
        }
        // 执行插入
        if (sqlite3_step(stmtMeta) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtMeta);
    }

private:
    std::string metaKey_;
    std::string metaValue_;
    const char *sqlCreateKindMeta = "CREATE TABLE IF NOT EXISTS Meta ("
                                    "name TEXT,"
                                    "value TEXT);";
    const char *sqlInsertKindMeta = "INSERT INTO Meta (name, value) VALUES (?, ?);";
};

}  // namespace msServiceProfiler

#endif  // SERVICE_PROFILER_DB_EXECUTOR_META_H
