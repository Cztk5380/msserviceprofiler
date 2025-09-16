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

#include <functional>
#include <memory>
#include <string>
#include <map>
#include <fstream>
#include <utility>
#include <mutex>

#include <sqlite3.h>
#include "DBExecutor/DbDefines.h"
#include "DbBuffer.h"
#include "Log.h"

namespace msServiceProfiler {

enum DBPriorityLevel : int {
    PRIORITY_START_PROF = -10,
    PRIORITY_NORMAL = 0,
    PRIORITY_STOP_PROF = 10,
};

class ServiceProfilerDbWriter;
class DbExecutorInterface {
public:
    virtual void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) = 0;
    virtual bool Cache() = 0;
    virtual int Level()
    {
        return PRIORITY_NORMAL;
    };
    virtual ~DbExecutorInterface() = default;
};

template <int T>
class DbExecutor final : public DbExecutorInterface {
public:
    void Execute(ServiceProfilerDbWriter &, sqlite3 *) override{};
    bool Cache() override
    {
        return false;
    };
    ~DbExecutor() override = default;
};

class DbFuncExec final : public DbExecutorInterface {
public:
    explicit DbFuncExec(std::function<void(ServiceProfilerDbWriter &, sqlite3 *)> func, int level = PRIORITY_NORMAL)
        : func_(std::move(func)), level_(level)
    {}
    void Execute(ServiceProfilerDbWriter &writer, sqlite3 *db) override
    {
        if (func_) {
            func_(writer, db);
        }
    };
    bool Cache() override
    {
        return false;
    };
    int Level() override
    {
        return level_;
    }
    ~DbFuncExec() override = default;

private:
    std::function<void(ServiceProfilerDbWriter &, sqlite3 *)> func_{};
    int level_ = PRIORITY_NORMAL;
};

using DBExecBuffer = DbBuffer<DbExecutorInterface>;

class ServiceProfilerDbWriter {
public:
    explicit ServiceProfilerDbWriter(const char *fileName) : dbFileName_(fileName)
    {
        this->thread_ = std::thread(&ServiceProfilerDbWriter::DumpThread, this);
    };
    ~ServiceProfilerDbWriter()
    {
        if (this->thread_.joinable()) {
            threadExitFlag_ = true;
            this->thread_.join();
        }
        std::lock_guard<std::mutex> lock(mtx_);
        StopDump();
        lifeEndFlag_ = true;
        workingDbBuffers_.clear();
        disableDbBuffers_.clear();
    };

    void StartDump(const std::string &outputPath);
    void StopDump();

    void DumpThread();

    // 只有register 和 unregister 是多线程竞争，其他都是通过 DBBuffer 过来的 Executor 执行，保证顺序，且不需要保护。
    std::shared_ptr<DBExecBuffer> Register(uintptr_t pThreadIns);
    void Unregister(uintptr_t pThreadIns);

public:
    sqlite3_stmt *GetStmt(const size_t stmtIndex) const
    {
        if (stmtIndex >= enableStmts_.size()) {
            return nullptr;
        }

        return enableStmts_[stmtIndex];
    }
    sqlite3_stmt *InitStmt(const size_t stmtIndex, const char *stmtStr)
    {
        if (stmtIndex >= enableStmts_.size() || db_ == nullptr || !inited) {
            return nullptr;
        }

        sqlite3_stmt *stmt = nullptr;
        if (sqlite3_prepare_v2(db_, stmtStr, -1, &stmt, nullptr) != SQLITE_OK) {
            PROF_LOGE("sqlInsertKindMstx SQL error");  // LCOV_EXCL_LINE
            return nullptr;
        }
        enableStmts_[stmtIndex] = stmt;
        return stmt;
    }
    void Execute(const char *sql) const;
    void CacheExecutor(std::unique_ptr<DbExecutorInterface> pExec)
    {
        cachedExecutor.push_back(std::move(pExec));
    }

private:
    void ApplyOptimizations() const;
    bool StartTransAction() const;
    void Flash() const;

private:
    int PopAndInsert2DB(const std::vector<std::shared_ptr<DBExecBuffer>> &workingDbBuffers,
        std::set<std::shared_ptr<DBExecBuffer>> &disableDbBuffers, std::vector<DBExecBuffer *> &freeDbBuffers);

private:
    std::mutex mtx_;
    std::thread thread_;
    bool lifeEndFlag_ = false;
    bool threadExitFlag_ = false;

private:
    std::map<uintptr_t, std::shared_ptr<DBExecBuffer>> mapBuffer_{};
    std::set<std::shared_ptr<DBExecBuffer>> disableDbBuffers_{};
    std::vector<std::shared_ptr<DBExecBuffer>> workingDbBuffers_{};

private:
    const char *dbFileName_ = nullptr;
    bool inited = false;
    sqlite3 *db_ = nullptr;
    std::vector<std::unique_ptr<DbExecutorInterface>> cachedExecutor{};
    std::array<sqlite3_stmt *, DB_STMT_CNT> enableStmts_{nullptr};
    std::map<int, std::vector<std::unique_ptr<DbExecutorInterface>>> cachePopExecutors_;
};

template <DBFile dbFile>
class ServiceProfilerDbFileWriter : public ServiceProfilerDbWriter {
    ServiceProfilerDbFileWriter() : ServiceProfilerDbWriter(DbFileName(dbFile)){};

public:
    static ServiceProfilerDbFileWriter &GetDbWriter()
    {
        static ServiceProfilerDbFileWriter manager;
        return manager;
    };
};

template <DBFile dbFile>
class ServiceProfilerThreadWriter {
public:
    ServiceProfilerThreadWriter()
    {
        pBuffer = ServiceProfilerDbFileWriter<dbFile>::GetDbWriter().Register((uintptr_t)this);
    }

    ~ServiceProfilerThreadWriter()
    {
        ServiceProfilerDbFileWriter<dbFile>::GetDbWriter().Unregister((uintptr_t)this);
    }

    static ServiceProfilerThreadWriter &GetWriter()
    {
        thread_local ServiceProfilerThreadWriter writer;
        return writer;
    }

    void Insert(std::unique_ptr<DbExecutorInterface> activity)
    {
        if (pBuffer) {
            auto pRetData = pBuffer->Push(std::move(activity));
            // pRetData 有值的话。表示存不进去了，目前不做什么处理，让他自动delete 好了
#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
            if (pRetData != nullptr) {
                thisThreadPushFailedCnt_++;
            }
            thisThreadPushCnt_++;
#endif
        }
    }

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
    void WaitForAllDump()
    {
        while (pBuffer->Size() > 0) {
            std::this_thread::sleep_for(std::chrono::nanoseconds(100));
        }
        PROF_LOGI(
            "buffer push: %lu, failed: %lu, pop cnt: %lu, push cnt: %lu, max cnt: %lu, diff: %lu",  // LCOV_EXCL_LINE
            thisThreadPushCnt_,
            thisThreadPushFailedCnt_,
            pBuffer->PopCnt(),
            pBuffer->PushCnt(),
            pBuffer->MaxCntInBuffer(),
            pBuffer->PushCnt() - pBuffer->PopCnt());
    }
#endif

private:
    std::shared_ptr<DBExecBuffer> pBuffer = nullptr;
#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
    size_t thisThreadPushCnt_ = 0;
    size_t thisThreadPushFailedCnt_ = 0;
#endif
};

template <DBFile dbFile>
void InsertExecutor2Writer(std::unique_ptr<DbExecutorInterface> activity)
{
    ServiceProfilerThreadWriter<dbFile>::GetWriter().Insert(std::move(activity));
}

}  // namespace msServiceProfiler

#endif  // SERVICEPROFILERDBWRITER_H
