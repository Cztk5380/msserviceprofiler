/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
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

    mode_t new_umask = 0137; // dbPath权限改成640
    mode_t old_umask = umask(new_umask);
    // 打开数据库连接
    int rc = sqlite3_open(dbPath.c_str(), &db_);
    if (rc != SQLITE_OK) {
        const char *errMsg = db_ ? sqlite3_errmsg(db_) : sqlite3_errstr(rc);
        PROF_LOGE("Execution failed: %s, %s", SecurityUtils::ToSafeString(errMsg).c_str(), SecurityUtils::ToSafeString(dbPath).c_str());  // LCOV_EXCL_LINE
        return;
    }
    umask(old_umask);

    ApplyOptimizations();
    inited = true;

    for (const auto &executor : cachedExecutor) {
        executor->Execute(*this, db_);
    }
}

void ServiceProfilerDbWriter::StopDump()
{
    // 释放资源
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

std::shared_ptr<DBExecBuffer> ServiceProfilerDbWriter::Register(uintptr_t pThreadIns)
{
    std::lock_guard<std::mutex> lock(mtx_);
    auto pBuffer = std::make_shared<DBExecBuffer>();
    mapBuffer_[pThreadIns] = pBuffer;
    workingDbBuffers_.push_back(pBuffer);
    return pBuffer;
}

void ServiceProfilerDbWriter::Unregister(uintptr_t pThreadIns)
{
    std::lock_guard<std::mutex> lock(mtx_);
    if (lifeEndFlag_) {
        return;
    }
    if (mapBuffer_.find(pThreadIns) != mapBuffer_.end()) {
        auto pBuffer = mapBuffer_.at(pThreadIns);
        mapBuffer_.erase(pThreadIns);
        disableDbBuffers_.insert(pBuffer);
    }
}

void ServiceProfilerDbWriter::DumpThread()
{
    constexpr int SUITABLE_DUMP_SIZE = 1000;
    constexpr int MAX_WAIT_US = 50000;  // 50ms
    constexpr int MIN_WAIT_US = 50;     // 50us
    int waitUs = MIN_WAIT_US;
    std::set<std::shared_ptr<DBExecBuffer>> disableDbBuffers;
    std::vector<std::shared_ptr<DBExecBuffer>> workingDbBuffers;
    while (!threadExitFlag_) {
        std::this_thread::sleep_for(std::chrono::microseconds(waitUs));
        {
            // 获取锁，并且看下列表是否有变化，有的话同步到函数变量中，处理的时候就可以释放锁
            std::lock_guard<std::mutex> lock(mtx_);
            if (workingDbBuffers.size() != workingDbBuffers_.size() ||
                disableDbBuffers.size() != disableDbBuffers_.size()) {
                disableDbBuffers = disableDbBuffers_;
                workingDbBuffers = workingDbBuffers_;
            }
        }
        std::vector<DBExecBuffer *> freeDbBuffers;
        auto popCount = PopAndInsert2DB(workingDbBuffers, disableDbBuffers, freeDbBuffers);

        // 更科学的从min和max之间转换
        double diff = std::max(std::min((SUITABLE_DUMP_SIZE - popCount) / 400.0, 2.5), -2.5);
        int diff_exp = static_cast<int>(exp(diff));  // 因为 diff 限制了范围，所以 exp diff 也不会超过 int 的范围
        waitUs = std::min(std::max(waitUs * diff_exp, MIN_WAIT_US), MAX_WAIT_US);  // 维持在写入1000条每次左右
        {
            std::lock_guard<std::mutex> lock(mtx_);

            for (auto *pBuffer : freeDbBuffers) {
                std::shared_ptr<DBExecBuffer> pTempBuffer(pBuffer, [](DBExecBuffer *) {});
                workingDbBuffers_.erase(std::remove(workingDbBuffers_.begin(), workingDbBuffers_.end(), pTempBuffer),
                    workingDbBuffers_.end());
                disableDbBuffers_.erase(pTempBuffer);
            }
            workingDbBuffers = workingDbBuffers_;
            disableDbBuffers = disableDbBuffers_;
        }
        if (popCount > 0) {
            PROF_LOGD("db write thread pop %d items", popCount);
        }
    }
}
}  // namespace msServiceProfiler

int msServiceProfiler::ServiceProfilerDbWriter::PopAndInsert2DB(
    const std::vector<std::shared_ptr<DBExecBuffer>> &workingDbBuffers,
    std::set<std::shared_ptr<DBExecBuffer>> &disableDbBuffers, std::vector<DBExecBuffer *> &freeDbBuffers)
{
    int popCount = 0;
    std::unique_ptr<DbExecutorInterface> *pMarkers = pPopMarkerBuffer.get();
    // pop
    for (const auto &pBuffer : workingDbBuffers) {
        size_t popSize = pBuffer->Pop(MAX_POP_SIZE, pMarkers);
        for (size_t i = 0; i < popSize; ++i) {
            if (pMarkers[i] == nullptr) {
                continue;
            }
            const int level = pMarkers[i]->Level();
            if (cachePopExecutors_.find(level) == cachePopExecutors_.end()) {
                cachePopExecutors_.emplace(level, std::vector<std::unique_ptr<DbExecutorInterface>>());
            }
            cachePopExecutors_.at(level).emplace_back(std::move(pMarkers[i]));

            pMarkers[i] = nullptr;
        }
        popCount += static_cast<int>(popSize);  // 数值不会太大，直接加没关系

        if (popSize == 0 && disableDbBuffers.find(pBuffer) != disableDbBuffers.end()) {
            freeDbBuffers.push_back(pBuffer.get());
        }
    }

    std::vector<int> levels;
    for (const auto &pair : cachePopExecutors_) {
        levels.push_back(pair.first);
    }
    std::sort(levels.begin(), levels.end());
    // insert
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
    return popCount;
}
