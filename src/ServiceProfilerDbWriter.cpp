/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#include <sys/types.h>
#include <unistd.h>
#include <semaphore.h>
#include <algorithm>
#include <atomic>
#include <mutex>
#include <chrono>
#include <climits>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
#include <map>
#include <cmath>
#include <sqlite3.h>
#include <functional>  // for std::hash
#include <sys/syscall.h>
#include <vector>
#include <set>
#include <cmath>
#include <forward_list>

#include "securec.h"
#include "acl/acl_prof.h"
#include "acl/acl.h"
#include "mstx/ms_tools_ext.h"

#include "msServiceProfiler/NpuMemoryUsage.h"
#include "msServiceProfiler/Profiler.h"
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/ServiceProfilerManager.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"
#include "msServiceProfiler/DbBuffer.h"

namespace {
constexpr int ALIGN_SIZE = 8;

}  // end of anonymous namespace

namespace msServiceProfiler {

uint32_t GetTid()
{
    return static_cast<uint32_t>(syscall(SYS_gettid));
}

std::string GetHostName()
{
    char hostname[HOST_NAME_MAX + 1] = {'\0'};  // 分配足够大的缓冲区
    if (gethostname(hostname, sizeof(hostname)) != 0) {
        PROF_LOGE("get hostname failed");
    }
    return std::string(hostname);
}

class ServiceProfilerDbWriter {
public:
    static ServiceProfilerDbWriter &GetInstance()
    {
        thread_local ServiceProfilerDbWriter manager;
        return manager;
    };

    void InsertMstxData(msServiceProfiler::DbActivityMarker *activity, bool enableTransAction = true) const
    {
        if (!inited || !activity || !stmtMstx_) {
            return;
        }

        if (enableTransAction) {
            // 开始事务
            StartTransAction();
        }

        // 绑定参数
        int bindIndex = 1;
        sqlite3_bind_text(stmtMstx_, bindIndex++, activity->message.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtMstx_, bindIndex++, static_cast<int64_t>(activity->flag));
        sqlite3_bind_int64(stmtMstx_, bindIndex++, static_cast<int64_t>(activity->id));
        sqlite3_bind_int64(stmtMstx_, bindIndex++, static_cast<int64_t>(activity->timestamp));
        sqlite3_bind_int64(stmtMstx_, bindIndex++, static_cast<int64_t>(activity->endTimestamp));
        sqlite3_bind_int64(stmtMstx_, bindIndex++, activity->processId);
        sqlite3_bind_int64(stmtMstx_, bindIndex++, activity->threadId);

        // 执行插入
        if (sqlite3_step(stmtMstx_) != SQLITE_DONE) {
            std::cerr << "Execution failed: " << sqlite3_errmsg(db_) << std::endl;
        }
        sqlite3_reset(stmtMstx_);

        if (enableTransAction) {
            // 提交最终事务
            Flash();
        }
    }
    void StartTransAction() const
    {
        // 开始事务
        if (db_ == nullptr || inited == false) {
            return;
        }
        char *errMsg = nullptr;
        if (sqlite3_exec(db_, "BEGIN TRANSACTION", nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE(" begin transaction error: %s", errMsg);
            sqlite3_free(errMsg);
        }
    }

    void Flash() const
    {
        // 提交最终事务
        char *errMsg = nullptr;
        if (db_ == nullptr || inited == false) {
            return;
        }
        if (sqlite3_exec(db_, "COMMIT", nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE(" commit error: %s", errMsg);
            sqlite3_free(errMsg);
        }
    }

    void InsertMetaData(const std::string &name, const std::string &value) const
    {
        if (!inited || !stmtMeta_) {
            return;
        }

        // 绑定参数
        int bindIndex = 1;
        sqlite3_bind_text(stmtMeta_, bindIndex++, name.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmtMeta_, bindIndex++, value.c_str(), -1, SQLITE_STATIC);

        // 执行插入
        if (sqlite3_step(stmtMeta_) != SQLITE_DONE) {
            std::cerr << "Execution failed: " << sqlite3_errmsg(db_) << std::endl;
        }
        sqlite3_reset(stmtMeta_);
    }

    void Init(const std::string &outputPath)
    {
        if (inited) {
            return;
        }
        auto hostName = GetHostName();
        uint32_t tid = GetTid();  // 每个线程有自己的副本
        std::string dbPath =
            outputPath + "ms_service_" + hostName + "-" + std::to_string(getpid()) + "-" + std::to_string(tid) + ".db";

        // 打开数据库连接
        int rc = sqlite3_open(dbPath.c_str(), &db_);
        if (rc != SQLITE_OK) {
            std::cerr << "Can't open database: " << sqlite3_errmsg(db_) << dbPath << std::endl;
            return;
        }
        CreateTable();
        ApplyOptimizations();
        inited = true;
        InsertMetaData("hostname", hostName);
    }

    void CreateTable()
    {
        char *errMsg = nullptr;
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

        if (sqlite3_exec(db_, sqlCreateKindMstx, nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE(" sqlCreateKindMstx SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db_, sqlInsertKindMstx, -1, &stmtMstx_, nullptr) != SQLITE_OK) {
            PROF_LOGE(" sqlInsertKindMstx SQL error");
        }

        const char *sqlCreateKindMeta = "CREATE TABLE IF NOT EXISTS Meta ("
                                        "name TEXT,"
                                        "value TEXT);";
        const char *sqlInsertKindMeta = "INSERT INTO Meta (name, value) VALUES (?, ?);";

        if (sqlite3_exec(db_, sqlCreateKindMeta, nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE(" sqlCreateKindMeta SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db_, sqlInsertKindMeta, -1, &stmtMeta_, nullptr) != SQLITE_OK) {
            PROF_LOGE(" sqlInsertKindMeta SQL error");
        }
    }

    void ApplyOptimizations() const
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
    }

    void Execute(const char *sql) const
    {
        char *errMsg = nullptr;
        if (sqlite3_exec(db_, sql, nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE(" Execution SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
    }

    void Close()
    {
        if (inited) {
            // 释放资源
            sqlite3_finalize(stmtMstx_);
            sqlite3_finalize(stmtMeta_);
            Execute("PRAGMA locking_mode = NORMAL;");  // 解除独占锁定模式（如果是独占）
            Execute("PRAGMA journal_mode = WAL;");     // 读写同步模式
            Execute("PRAGMA wal_checkpoint(FULL);");   // 执行检查点
            sqlite3_close(db_);
            db_ = nullptr;
            inited = false;
        }
    }

    ServiceProfilerDbWriter() : inited(false), db_(nullptr), stmtMstx_(nullptr), stmtMeta_(nullptr)
    {
        Init(msServiceProfiler::ServiceProfilerManager::GetInstance().GetProfPath());
    }

private:
    bool inited = false;
    sqlite3 *db_;
    sqlite3_stmt *stmtMstx_ = nullptr;
    sqlite3_stmt *stmtMeta_ = nullptr;
};
class ServiceProfilerThreadWriter;
class ServiceProfilerWriterManager {
public:
    static ServiceProfilerWriterManager &GetInstance()
    {
        static ServiceProfilerWriterManager manager;  // 进程级，永远不析构
        return manager;
    };

    DbBuffer *Register(ServiceProfilerThreadWriter *pThreadIns)
    {
        std::lock_guard<std::mutex> lock(mtx_);
        auto *pBuffer = new DbBuffer();
        mapBuffer_[pThreadIns] = pBuffer;
        workingDbBuffers_.push_back(pBuffer);
        return pBuffer;
    }

    void Unregister(ServiceProfilerThreadWriter *pThreadIns)
    {
        std::lock_guard<std::mutex> lock(mtx_);
        if (mapBuffer_.find(pThreadIns) != mapBuffer_.end()) {
            auto *pBuffer = mapBuffer_.at(pThreadIns);
            mapBuffer_.erase(pThreadIns);
            disableDbBuffers_.insert(pBuffer);
        }
    }

    void Start(const std::string &outputPath)
    {
        std::lock_guard<std::mutex> lock(mtx_);
        closeFlag_ = false;
        profPath_ = outputPath;
    }

    void Close()
    {
        std::lock_guard<std::mutex> lock(mtx_);
        closeFlag_ = true;
    }

    void ThreadFunction()
    {
        constexpr int SUITABLE_DUMP_SIZE = 1000;
        constexpr int MAX_WAIT_US = 50000;  // 50ms
        constexpr int MIN_WAIT_US = 50;     // 50us
        int waitUs = MIN_WAIT_US;
        std::set<DbBuffer *> disableDbBuffers;
        std::vector<DbBuffer *> workingDbBuffers;
        while (threadExitFlag_ == false) {
            std::this_thread::sleep_for(std::chrono::microseconds(waitUs));
            {
                // 获取锁，并且看下列表是否有变化，有的话同步到函数变量中，处理的时候就可以释放锁
                std::lock_guard<std::mutex> lock(mtx_);
                if (workingDbBuffers.size() != workingDbBuffers_.size() ||
                    disableDbBuffers.size() != disableDbBuffers_.size()) {
                    disableDbBuffers = disableDbBuffers_;
                    workingDbBuffers = workingDbBuffers_;
                }

                // 如果还开启，尝试Init 一下，已经 Init 过会有标记，不会重复Init
                if (!closeFlag_) {
                    ServiceProfilerDbWriter::GetInstance().Init(profPath_);
                }
            }
            std::vector<DbBuffer *> freeDbBuffers;
            auto popCount = PopAndInsert2DB(workingDbBuffers, disableDbBuffers, freeDbBuffers);

            // 更科学的从min和max之间转换
            double diff = std::max(std::min((SUITABLE_DUMP_SIZE - popCount) / 400.0, 2.5), -2.5);
            int diff_exp = static_cast<int>(exp(diff));  // 因为 diff 限制了范围，所以 exp diff 也不会超过 int 的范围
            waitUs = std::min(std::max(waitUs * diff_exp, MIN_WAIT_US), MAX_WAIT_US);  // 维持在写入1000条每次左右
            bool dbCloseFlag = false;
            {
                std::lock_guard<std::mutex> lock(mtx_);

                for (auto *pBuffer : freeDbBuffers) {
                    workingDbBuffers_.erase(std::remove(workingDbBuffers_.begin(), workingDbBuffers_.end(), pBuffer),
                        workingDbBuffers_.end());
                    disableDbBuffers_.erase(pBuffer);
                    delete pBuffer;
                }
                workingDbBuffers = workingDbBuffers_;
                disableDbBuffers = disableDbBuffers_;

                if (popCount == 0 && closeFlag_) {
                    dbCloseFlag = true;
                }
            }
            if (dbCloseFlag) {
                ServiceProfilerDbWriter::GetInstance().Close();
            }
        }
    }

private:
    ServiceProfilerWriterManager()
    {
        this->thread_ = std::thread(&ServiceProfilerWriterManager::ThreadFunction, this);
    }
    ~ServiceProfilerWriterManager()
    {
        if (this->thread_.joinable()) {
            threadExitFlag_ = true;
            this->thread_.join();
        }
        std::lock_guard<std::mutex> lock(mtx_);

        for (auto *pBuffer : workingDbBuffers_) {
            delete pBuffer;
        }
        workingDbBuffers_.clear();
        disableDbBuffers_.clear();
    }

    int PopAndInsert2DB(std::vector<DbBuffer *> &workingDbBuffers, std::set<DbBuffer *> &disableDbBuffers,
        std::vector<DbBuffer *> &freeDbBuffers)
    {
        constexpr size_t MAX_POP_SIZE = 2000;
        int popCount = 0;
        ServiceProfilerDbWriter::GetInstance().StartTransAction();
        for (DbBuffer *pbuffer : workingDbBuffers) {
            DbActivityMarkerPtr pMarkers[MAX_POP_SIZE] = {nullptr};

            size_t popSize = pbuffer->Pop(MAX_POP_SIZE, pMarkers);
            for (size_t i = 0; i < popSize; ++i) {
                if (pMarkers[i] == nullptr) {
                    continue;
                }
                ServiceProfilerDbWriter::GetInstance().InsertMstxData(pMarkers[i], false);
                delete pMarkers[i];
                pMarkers[i] = nullptr;
            }
            popCount += popSize;

            if (popSize == 0 && disableDbBuffers.find(pbuffer) != disableDbBuffers.end()) {
                freeDbBuffers.push_back(pbuffer);
            }
        }
        ServiceProfilerDbWriter::GetInstance().Flash();
        return popCount;
    }

private:
    std::mutex mtx_;
    std::map<ServiceProfilerThreadWriter *, DbBuffer *> mapBuffer_;
    std::thread thread_;
    std::set<DbBuffer *> disableDbBuffers_;
    std::vector<DbBuffer *> workingDbBuffers_;
    bool closeFlag_ = false;
    bool threadExitFlag_ = false;
    std::string profPath_;
};

class ServiceProfilerThreadWriter {
public:
    ServiceProfilerThreadWriter()
    {
        pBuffer = ServiceProfilerWriterManager::GetInstance().Register(this);
    }
    ~ServiceProfilerThreadWriter()
    {
        ServiceProfilerWriterManager::GetInstance().Unregister(this);
    }
    void Insert(msServiceProfiler::DbActivityMarker *activity)
    {
        if (pBuffer) {
            pBuffer->Push(activity);

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
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
        PROF_LOGI("buffer i push: %lu, pop cnt: %lu, push cnt: %lu, max cnt: %lu, diff: %lu",
            thisThreadPushCnt_,
            pBuffer->PopCnt(),
            pBuffer->PushCnt(),
            pBuffer->MaxCntInBuffer(),
            pBuffer->PushCnt() - pBuffer->PopCnt());
    }
#endif

private:
    DbBuffer *pBuffer = nullptr;
#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
    size_t thisThreadPushCnt_ = 0;
#endif
};

ServiceProfilerThreadWriter &GetWriter()
{
    thread_local ServiceProfilerThreadWriter writer;
    return writer;
}

void InsertTxData2Writer(msServiceProfiler::DbActivityMarker *activity)
{
    GetWriter().Insert(activity);
}

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
void WaitForAllDump()
{
    GetWriter().WaitForAllDump();
}
#endif

void CloseTxData2Writer()
{
    ServiceProfilerWriterManager::GetInstance().Close();
}

void StartTxData2Writer(const std::string &outputPath)
{
    ServiceProfilerWriterManager::GetInstance().Start(outputPath);
}
}  // namespace msServiceProfiler
