/* -------------------------------------------------------------------------
 * 版权所有 (c) 华为技术有限公司 2023-2025
 * Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
 * Create Date : 2023
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

#ifndef SERVICE_PROFILER_DB_EXECUTOR_SLICE_DATA_H
#define SERVICE_PROFILER_DB_EXECUTOR_SLICE_DATA_H

#include <cstdint>
#include <string>
#include <sqlite3.h>
#include <cstdio>

#include "../Log.h"
#include "../ServiceProfilerDbWriter.h"
#include "./DbDefines.h"

namespace msServiceProfiler {
struct DbSliceData {
    uint64_t timestamp;      // 起始时间
    uint64_t duration;       // 持续时间
    std::string name;        // 事件/跨度名称
    int32_t depth;           // 嵌套深度
    int64_t track_id;        // 关联到
    std::string cat;         // 分类
    std::string args;        // 额外参数
    std::string cname;       // 颜色名
    uint64_t end_time;       // 结束时间
    std::string flag_id;     // 自定义标识
    int64_t pid;             // 进程 ID
    int64_t tid;             // 线程 ID
};

template <>
class DbExecutor<SLICE_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(DbSliceData &&sliceData) : slice(std::move(sliceData)) {
    }

    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmt = writer.GetStmt(SLICE_INSERT_STMT);
        if (stmt == nullptr) {
            writer.Execute(sqlCreateSlice);
            stmt = writer.InitStmt(SLICE_INSERT_STMT, sqlInsertSlice);
            if (stmt == nullptr) {
                return;
            }
        }
        if (db == nullptr) {
            return;
        }
        InsertSliceData(db, stmt);
    }

    bool Cache() override
    {
        return false;
    }

private:
    bool BindSliceFields(sqlite3 *db, sqlite3_stmt *stmt) const
    {
        int bindIndex = 0;

        // 辅助 lambda：统一处理绑定结果检查
        auto bindCheck = [&](int result, int index) -> bool {
            if (result != SQLITE_OK) {
                PROF_LOGE("bind failed:%d %s", index, sqlite3_errmsg(db));
                sqlite3_reset(stmt);
                return false;
            }
            return true;
        };

        // timestamp
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_int64(stmt, bindIndex, static_cast<int64_t>(slice.timestamp)), bindIndex))
            return false;

        // duration
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_int64(stmt, bindIndex, static_cast<int64_t>(slice.duration)), bindIndex))
            return false;

        // name
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_text(stmt, bindIndex, slice.name.c_str(), -1, SQLITE_STATIC), bindIndex))
            return false;

        // depth
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_int64(stmt, bindIndex, slice.depth), bindIndex))
            return false;

        // track_id
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_int64(stmt, bindIndex, slice.track_id), bindIndex))
            return false;

        // cat
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_text(stmt, bindIndex, slice.cat.c_str(), -1, SQLITE_STATIC), bindIndex))
            return false;

        // args
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_text(stmt, bindIndex, slice.args.c_str(), -1, SQLITE_STATIC), bindIndex))
            return false;

        // cname
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_text(stmt, bindIndex, slice.cname.c_str(), -1, SQLITE_STATIC), bindIndex))
            return false;

        // end_time
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_int64(stmt, bindIndex, static_cast<int64_t>(slice.end_time)), bindIndex))
            return false;

        // flag_id
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_text(stmt, bindIndex, slice.flag_id.c_str(), -1, SQLITE_STATIC), bindIndex))
            return false;

        // pid
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_int64(stmt, bindIndex, slice.pid), bindIndex))
            return false;

        // tid
        ++bindIndex;
        if (!bindCheck(sqlite3_bind_int64(stmt, bindIndex, slice.tid), bindIndex))
            return false;

        return true;
    }

    void InsertSliceData(sqlite3 *db, sqlite3_stmt *stmt) const
    {
        if (!BindSliceFields(db, stmt)) {
            return;
        }

        if (sqlite3_step(stmt) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmt);
    }

private:
    DbSliceData slice;

    static constexpr const char *sqlCreateSlice =
        "CREATE TABLE IF NOT EXISTS slice ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "timestamp INTEGER, "
        "duration INTEGER, "
        "name TEXT, "
        "depth INTEGER, "
        "track_id INTEGER, "
        "cat TEXT, "
        "args TEXT, "
        "cname TEXT, "
        "end_time INTEGER, "
        "flag_id TEXT, "
        "pid INTEGER, "
        "tid INTEGER);";

    static constexpr const char *sqlInsertSlice =
        "INSERT INTO slice ("
        "timestamp, duration, name, depth, track_id, cat, args, cname, end_time, flag_id, "
        "pid, tid"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);";
};

// ========== Counter Table Executor ==========
struct DbCounterData {
    std::string name;
    std::string pid;
    uint64_t timestamp;
    std::string cat;
    std::string args;
};

template <>
class DbExecutor<COUNTER_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(DbCounterData &&data) : counterData(std::move(data)) {
    }

    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmt = writer.GetStmt(COUNTER_INSERT_STMT);
        if (stmt == nullptr) {
            writer.Execute(sqlCreateCounter);
            stmt = writer.InitStmt(COUNTER_INSERT_STMT, sqlInsertCounter);
            if (stmt == nullptr) {
                return;
            }
        }
        if (db == nullptr) {
            return;
        }
        InsertCounterData(db, stmt);
    }

    bool Cache() override
    {
        return false;
    }

private:
    void InsertCounterData(sqlite3 *db, sqlite3_stmt *stmt) const
    {
        int bindIndex = 0;
        if (sqlite3_bind_text(stmt, ++bindIndex, counterData.name.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, counterData.pid.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_int64(stmt, ++bindIndex, static_cast<int64_t>(counterData.timestamp)) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, counterData.cat.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, counterData.args.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_step(stmt) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));
        }
        sqlite3_reset(stmt);
    }

private:
    DbCounterData counterData;
    static constexpr const char *sqlCreateCounter =
        "CREATE TABLE IF NOT EXISTS counter ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT, pid TEXT, timestamp INTEGER, cat TEXT, args TEXT);";

    static constexpr const char *sqlInsertCounter =
        "INSERT INTO counter "
        "(name, pid, timestamp, cat, args) "
        "VALUES (?, ?, ?, ?, ?);";
};

// ========== Flow Table Executor ==========
struct DbFlowData {
    std::string flow_id;
    std::string name;
    std::string cat;
    int64_t track_id;
    uint64_t timestamp;
    std::string type;
};

template <>
class DbExecutor<FLOW_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(DbFlowData &&data) : flowData(std::move(data)) {
    }

    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmt = writer.GetStmt(FLOW_INSERT_STMT);
        if (stmt == nullptr) {
            writer.Execute(sqlCreateFlow);
            stmt = writer.InitStmt(FLOW_INSERT_STMT, sqlInsertFlow);
            if (stmt == nullptr) {
                return;
            }
        }
        if (db == nullptr) {
            return;
        }
        InsertFlowData(db, stmt);
    }

    bool Cache() override
    {
        return false;
    }

private:
    void InsertFlowData(sqlite3 *db, sqlite3_stmt *stmt) const
    {
        int bindIndex = 0;
        if (sqlite3_bind_text(stmt, ++bindIndex, flowData.flow_id.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, flowData.name.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, flowData.cat.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_int64(stmt, ++bindIndex, flowData.track_id) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_int64(stmt, ++bindIndex, static_cast<int64_t>(flowData.timestamp)) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, flowData.type.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_step(stmt) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));
        }
        sqlite3_reset(stmt);
    }

private:
    DbFlowData flowData;
    static constexpr const char *sqlCreateFlow =
        "CREATE TABLE IF NOT EXISTS flow ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "flow_id TEXT, name TEXT, cat TEXT, track_id INTEGER, timestamp INTEGER, type TEXT);";

    static constexpr const char *sqlInsertFlow =
        "INSERT INTO flow "
        "(flow_id, name, cat, track_id, timestamp, type) "
        "VALUES (?, ?, ?, ?, ?, ?);";
};

// ========== Process Table Executor ==========
struct DbProcessData {
    std::string pid;
    std::string process_name;
    std::string label;
    int64_t process_sort_index;
    std::string parentPid;
};

template <>
class DbExecutor<PROCESS_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(DbProcessData &&data) : processData(std::move(data)) {
    }

    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmt = writer.GetStmt(PROCESS_INSERT_STMT);
        if (stmt == nullptr) {
            writer.Execute(sqlCreateProcess);
            stmt = writer.InitStmt(PROCESS_INSERT_STMT, sqlInsertProcess);
            if (stmt == nullptr) {
                return;
            }
        }
        if (db == nullptr) {
            return;
        }
        InsertProcessData(db, stmt);
    }

    bool Cache() override
    {
        return false;
    }

private:
    void InsertProcessData(sqlite3 *db, sqlite3_stmt *stmt) const
    {
        int bindIndex = 0;
        if (sqlite3_bind_text(stmt, ++bindIndex, processData.pid.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, processData.process_name.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, processData.label.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_int64(stmt, ++bindIndex, processData.process_sort_index) != SQLITE_OK) {
            PROF_LOGE("bind failed: %d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, processData.parentPid.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed: %d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_step(stmt) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));
        }
        sqlite3_reset(stmt);
    }

private:
    DbProcessData processData;
    static constexpr const char *sqlCreateProcess =
        "CREATE TABLE IF NOT EXISTS process ("
        "pid TEXT PRIMARY KEY,"
        "process_name TEXT,"
        "label TEXT,"
        "process_sort_index INTEGER,"
        "parentPid TEXT"
        ");";

    static constexpr const char *sqlInsertProcess =
        "INSERT INTO process "
        "(pid, process_name, label, process_sort_index, parentPid) "
        "VALUES (?, ?, ?, ?, ?);";
};

// ========== Thread Table Executor ==========
struct DbThreadData {
    int64_t track_id;
    std::string tid;
    std::string pid;
    std::string thread_name;
    int64_t thread_sort_index;
};

template <>
class DbExecutor<THREAD_INSERT_STMT> : public DbExecutorInterface {
public:
    explicit DbExecutor(DbThreadData &&data) : threadData(std::move(data)) {
    }

    ~DbExecutor() override = default;

    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        sqlite3_stmt *stmt = writer.GetStmt(THREAD_INSERT_STMT);
        if (stmt == nullptr) {
            writer.Execute(sqlCreateThread);
            stmt = writer.InitStmt(THREAD_INSERT_STMT, sqlInsertThread);
            if (stmt == nullptr) {
                return;
            }
        }
        if (db == nullptr) {
            return;
        }
        InsertThreadData(db, stmt);
    }

    bool Cache() override
    {
        return false;
    }

private:
    void InsertThreadData(sqlite3 *db, sqlite3_stmt *stmt) const
    {
        int bindIndex = 0;
        if (sqlite3_bind_int64(stmt, ++bindIndex, threadData.track_id) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, threadData.tid.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, threadData.pid.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_text(stmt, ++bindIndex, threadData.thread_name.c_str(), -1, SQLITE_STATIC) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_bind_int64(stmt, ++bindIndex, threadData.thread_sort_index) != SQLITE_OK) {
            PROF_LOGE("bind failed:%d %s", bindIndex, sqlite3_errmsg(db));
            sqlite3_reset(stmt);
            return;
        }
        if (sqlite3_step(stmt) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db));
        }
        sqlite3_reset(stmt);
    }

private:
    DbThreadData threadData;
    static constexpr const char *sqlCreateThread =
        "CREATE TABLE IF NOT EXISTS thread ("
        "track_id INTEGER PRIMARY KEY,"
        "tid TEXT,"
        "pid TEXT,"
        "thread_name TEXT,"
        "thread_sort_index INTEGER"
        ");";

    static constexpr const char *sqlInsertThread =
        "INSERT INTO thread "
        "(track_id, tid, pid, thread_name, thread_sort_index) "
        "VALUES (?, ?, ?, ?, ?);";
};

}  // namespace msServiceProfiler

#endif  // SERVICE_PROFILER_DB_EXECUTOR_SLICE_DATA_H