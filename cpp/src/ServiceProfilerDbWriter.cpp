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

#include <sys/types.h>
#include <unistd.h>
#include <semaphore.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <climits>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
#include <map>
#include <cmath>
#include <functional>
#include <algorithm>
#include <set>
#include <cmath>
#include <forward_list>
#include <sqlite3.h>
#include <sys/stat.h>

#include "securec.h"
#include "acl/acl_prof.h"
#include "acl/acl.h"
#include "mstx/ms_tools_ext.h"

#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/DbBuffer.h"
#include "msServiceProfiler/Profiler.h"
#include "msServiceProfiler/NpuMemoryUsage.h"
#include "msServiceProfiler/SecurityUtilsLog.h"
#include "msServiceProfiler/ServiceProfilerManager.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"

namespace {
constexpr int ALIGN_SIZE = 8;

}  // end of anonymous namespace

namespace msServiceProfiler {

bool ServiceProfilerDbWriter::StartTransAction() const
{
    // 开始事务
    if (db_ == nullptr || !inited) {
        return false;
    }
    char *errMsg = nullptr;
    if (sqlite3_exec(db_, "BEGIN TRANSACTION", nullptr, nullptr, &errMsg) != SQLITE_OK) {
        PROF_LOGE(" begin transaction error: %s", errMsg);  // LCOV_EXCL_LINE
        sqlite3_free(errMsg);
        return false;
    }
    return true;
}

void ServiceProfilerDbWriter::Flash() const
{
    // 提交最终事务
    char *errMsg = nullptr;
    if (db_ == nullptr || !inited) {
        return;
    }
    if (sqlite3_exec(db_, "COMMIT", nullptr, nullptr, &errMsg) != SQLITE_OK) {
        PROF_LOGE(" commit error: %s", errMsg);  // LCOV_EXCL_LINE
        sqlite3_free(errMsg);
    }
}

void ServiceProfilerDbWriter::StartDump(const std::string &outputPath)
{
    if (inited) {
        return;
    }
    const auto &hostName = MsUtils::GetHostName();

    std::string dbPath = outputPath + dbFileName_ + "_" + hostName + "-" + std::to_string(getpid()) + ".db";

    MsUtils::UmaskGuard umaskGuard;
    // 打开数据库连接
    int rc = sqlite3_open(dbPath.c_str(), &db_);
    if (rc != SQLITE_OK) {
        const char *errMsg = db_ ? sqlite3_errmsg(db_) : sqlite3_errstr(rc);
        PROF_LOGE("Execution failed: %s, %s", SecurityUtils::ToSafeString(errMsg).c_str(), SecurityUtils::ToSafeString(dbPath).c_str());  // LCOV_EXCL_LINE
        return;
    }

    ApplyOptimizations();
    inited = true;

    for (const auto &executor : cachedExecutor) {
        executor->Execute(*this, db_);
    }
}

void ServiceProfilerDbWriter::StopDump()
{
    // 释放资源
    PROF_LOGD("Service Profiler DbWriter StopDump");
    for (auto &enableStmt : enableStmts_) {
        auto *stmt = enableStmt;
        if (stmt != nullptr) {
            sqlite3_finalize(stmt);
        }
        enableStmt = nullptr;
    }
    if (db_) {
        Execute("PRAGMA locking_mode = NORMAL;");  // 解除独占锁定模式（如果是独占）
        Execute("PRAGMA journal_mode = WAL;");     // 读写同步模式
        Execute("PRAGMA wal_checkpoint(FULL);");   // 执行检查点
        sqlite3_close(db_);
        db_ = nullptr;
    }
    inited = false;
}

void ServiceProfilerDbWriter::ApplyOptimizations() const
{
    // 组合优化设置
    // 测试时长 10s, 每 1ms 写入 [speed] 数据，每个数据50+ bit 数据
    // 200+ 单线程的prof生产的速度已经跟不上dump速度，单线程已经没有意义

    // journal_mode     locking_mode   batch         speed          tread*speed         note
    // ------------     ------------   -----------   ------------   ------------        ------------
    // TRUNCATE         EXCLUSIVE      Disable       40
    // WAL              EXCLUSIVE      Disable       70+
    // OFF              EXCLUSIVE      Disable       110+                               OFF容易损坏db
    // MEMORY           EXCLUSIVE      Disable       100
    // MEMORY           EXCLUSIVE      Enable        200+           2*180/3*130/4*100   EXCLUSIVE会阻塞读取
    // MEMORY           NORMAL         Disable       50
    // WAL              NORMAL         Disable       60
    // WAL              NORMAL         Enable        200+           2*160/3*100/4*80    选择这个

    Execute("PRAGMA journal_mode = WAL;");     // 读写同步模式
    Execute("PRAGMA synchronous = OFF;");      // 急速模式
    Execute("PRAGMA cache_size = -1000;");     // 1MB缓存
    Execute("PRAGMA temp_store = MEMORY;");    // 内存临时存储
    Execute("PRAGMA page_size = 4096;");       // 页面大小
    Execute("PRAGMA locking_mode = NORMAL;");  // 非独占锁定模式

    PROF_LOGD("DB set to WAL mode.");
}

void ServiceProfilerDbWriter::Execute(const char *sql) const
{
    if (db_ == nullptr || !inited) {
        return;
    }
    char *errMsg = nullptr;
    auto execRet = sqlite3_exec(db_, sql, nullptr, nullptr, &errMsg);
    if (execRet != SQLITE_OK) {
        PROF_LOGE(" Execution SQL error: [%d][%s], and the sql is [%s]", execRet, errMsg, sql);  // LCOV_EXCL_LINE
        sqlite3_free(errMsg);
    }
}

void msServiceProfiler::ServiceProfilerDbWriter::RecvDbExecutor(std::unique_ptr<DbExecutorInterface> dbExecutor)
{
    const int level = dbExecutor->Level();
    if (cachePopExecutors_.find(level) == cachePopExecutors_.end()) {
        cachePopExecutors_.emplace(level, std::vector<std::unique_ptr<DbExecutorInterface>>());
    }
    cachePopExecutors_.at(level).emplace_back(std::move(dbExecutor));
}

void msServiceProfiler::ServiceProfilerDbWriter::ExecutorDumpToDb()
{
    std::vector<int> levels;
    for (const auto &pair : cachePopExecutors_) {
        levels.push_back(pair.first);
    }
    std::sort(levels.begin(), levels.end());
    // insert
    std::lock_guard<std::mutex> lock(mtx_);
    bool started = false;
    for (int level : levels) {
        if (!started && level == PRIORITY_NORMAL) {
            started = StartTransAction();
        }
        for (auto it = cachePopExecutors_[level].begin(); it != cachePopExecutors_[level].end(); ++it) {
            std::unique_ptr<DbExecutorInterface> &executor = *it;
            executor->Execute(*this, this->db_);
            if (executor->Cache()) {
                CacheExecutor(std::move(executor));
            }
        }

        cachePopExecutors_[level].clear();
        if (started && level == PRIORITY_NORMAL) {
            Flash();
            started = false;
        }
    }
}
}  // namespace msServiceProfiler
