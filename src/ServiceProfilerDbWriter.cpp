/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#include <sys/types.h>
#include <unistd.h>
#include <sys/syscall.h>
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
#include <sqlite3.h>
#include <functional>  // for std::hash
#include "securec.h"
#include "acl/acl_prof.h"
#include "acl/acl.h"
#include "mstx/ms_tools_ext.h"
#include "msServiceProfiler/NpuMemoryUsage.h"
#include "msServiceProfiler/Profiler.h"
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/ServiceProfilerManager.h"
#include "msServiceProfiler/DbBuffer.h"
#include "msServiceProfiler/DbBuffer.h"

namespace msServiceProfiler {

uint32_t GetTid()
{
    return static_cast<uint32_t>(syscall(SYS_gettid));
}

std::string GetHostName()
{
    char hostname[HOST_NAME_MAX + 1] = {'\0'};  // 分配足够大的缓冲区
    if (gethostname(hostname, sizeof(hostname)) != 0) {
        PROF_LOGE("get hostname failed"); // LCOV_EXCL_LINE
    }
    return std::string(hostname);
}

ServiceProfilerDbWriter &ServiceProfilerDbWriter::GetInstance()
{
    thread_local ServiceProfilerDbWriter manager;
    return manager;
}

void ServiceProfilerDbWriter::InsertMstxData(DbActivityMarker *activity) const
{
    if (!inited || !activity || !stmtMstx_) {
        return;
    }

    // 开始事务
    sqlite3_exec(db_, "BEGIN TRANSACTION", nullptr, nullptr, nullptr);

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
        PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db_)); // LCOV_EXCL_LINE
    }
    sqlite3_reset(stmtMstx_);

    // 提交最终事务
    sqlite3_exec(db_, "COMMIT", nullptr, nullptr, nullptr);
}

void ServiceProfilerDbWriter::Flash() const
{
    // 提交最终事务
    sqlite3_exec(db_, "COMMIT", nullptr, nullptr, nullptr);
}

void ServiceProfilerDbWriter::InsertMetaData(const std::string &name, const std::string &value) const
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
        PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db_)); // LCOV_EXCL_LINE
    }
    sqlite3_reset(stmtMeta_);
}

void ServiceProfilerDbWriter::Init(const std::string &outputPath)
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
        PROF_LOGE("Execution failed: %s", sqlite3_errmsg(db_)); // LCOV_EXCL_LINE
        return;
    }
    CreateTable();
    ApplyOptimizations();
    inited = true;
    InsertMetaData("hostname", hostName);
}

void ServiceProfilerDbWriter::CreateTable()
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
        PROF_LOGE(" sqlCreateKindMstx SQL error: %s", errMsg); // LCOV_EXCL_LINE
        sqlite3_free(errMsg);
    }
    if (sqlite3_prepare_v2(db_, sqlInsertKindMstx, -1, &stmtMstx_, nullptr) != SQLITE_OK) {
        PROF_LOGE(" sqlInsertKindMstx SQL error"); // LCOV_EXCL_LINE
    }

    const char *sqlCreateKindMeta = "CREATE TABLE IF NOT EXISTS Meta ("
                                    "name TEXT,"
                                    "value TEXT);";
    const char *sqlInsertKindMeta = "INSERT INTO Meta (name, value) VALUES (?, ?);";

    if (sqlite3_exec(db_, sqlCreateKindMeta, nullptr, nullptr, &errMsg) != SQLITE_OK) {
        PROF_LOGE(" sqlCreateKindMeta SQL error: %s", errMsg); // LCOV_EXCL_LINE
        sqlite3_free(errMsg);
    }
    if (sqlite3_prepare_v2(db_, sqlInsertKindMeta, -1, &stmtMeta_, nullptr) != SQLITE_OK) {
        PROF_LOGE(" sqlInsertKindMeta SQL error"); // LCOV_EXCL_LINE
    }
}

void ServiceProfilerDbWriter::ApplyOptimizations() const
{
    // 组合优化设置
    Execute("PRAGMA journal_mode = WAL;");     // 急速模式（非）
    Execute("PRAGMA synchronous = OFF;");      // 急速模式
    Execute("PRAGMA cache_size = -1000;");     // 1MB缓存
    Execute("PRAGMA temp_store = MEMORY;");    // 内存临时存储
    Execute("PRAGMA page_size = 4096;");       // 页面大小
    Execute("PRAGMA locking_mode = NORMAL;");  // 独占锁定模式(非)
}

void ServiceProfilerDbWriter::Execute(const char *sql) const
{
    char *errMsg = nullptr;
    if (sqlite3_exec(db_, sql, nullptr, nullptr, &errMsg) != SQLITE_OK) {
        PROF_LOGE(" Execution SQL error: %s", errMsg); // LCOV_EXCL_LINE
        sqlite3_free(errMsg);
    }
}

void ServiceProfilerDbWriter::Close()
{
    if (inited) {
        // 释放资源
        sqlite3_finalize(stmtMstx_);
        Execute("PRAGMA wal_checkpoint(FULL);");  // 执行检查点
        sqlite3_close(db_);
        inited = false;
    }
}

ServiceProfilerDbWriter::ServiceProfilerDbWriter() : inited(false), db_(nullptr), stmtMstx_(nullptr), stmtMeta_(nullptr)
{
    Init(msServiceProfiler::ServiceProfilerManager::GetInstance().GetProfPath());
}

ServiceProfilerDbWriter::~ServiceProfilerDbWriter()
{
    Close();
}

ServiceProfilerWriterManager &ServiceProfilerWriterManager::GetInstance() {
    static ServiceProfilerWriterManager manager;  // 进程级，永远不析构
    return manager;
}

DbBuffer *ServiceProfilerWriterManager::Register(ServiceProfilerThreadWriter *pThreadIns) {
    std::lock_guard<std::mutex> lock(mtx_);
    auto *pBuffer = new DbBuffer();
    mapBuffer_[pThreadIns] = pBuffer;
    workingDbBuffers_.push_back(pBuffer);
    return pBuffer;
}

void ServiceProfilerWriterManager::Unregister(ServiceProfilerThreadWriter *pThreadIns) {
    std::lock_guard<std::mutex> lock(mtx_);
    if (mapBuffer_.find(pThreadIns) != mapBuffer_.end()) {
        auto *pBuffer = mapBuffer_.at(pThreadIns);
        mapBuffer_.erase(pThreadIns);
        disableDbBuffers_.insert(pBuffer);
    }
}

void ServiceProfilerWriterManager::Start(const std::string &outputPath) {
    std::lock_guard<std::mutex> lock(mtx_);
    closeFlag_ = false;
    profPath_ = outputPath;
}

void ServiceProfilerWriterManager::Close() {
    std::lock_guard<std::mutex> lock(mtx_);
    closeFlag_ = true;
}

void ServiceProfilerWriterManager::ThreadFunction() {
    constexpr int SUITABLE_DUMP_SIZE = 1000;
    constexpr int MAX_WAIT_US = 50000;  // 50ms
    constexpr int MIN_WAIT_US = 50;     // 50us
    int waitUs = MAX_WAIT_US;
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

        waitUs = std::min(std::max(waitUs - (popCount - SUITABLE_DUMP_SIZE) / 10, MIN_WAIT_US),
                          MAX_WAIT_US);  // 维持在写入1000条每次左右
        bool dbCloseFlag = false;
        {
            std::lock_guard<std::mutex> lock(mtx_);

            for (auto *pBuffer : freeDbBuffers) {
                workingDbBuffers_.erase(std::remove(workingDbBuffers_.begin(), workingDbBuffers_.end(), pBuffer),
                                        workingDbBuffers_.end());
                disableDbBuffers_.erase(pBuffer);
                free(pBuffer);
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

ServiceProfilerWriterManager::ServiceProfilerWriterManager() {
    this->thread_ = std::thread(&ServiceProfilerWriterManager::ThreadFunction, this);
}

ServiceProfilerWriterManager::~ServiceProfilerWriterManager() {
    if (this->thread_.joinable()) {
        threadExitFlag_ = true;
        this->thread_.join();
    }
}

int ServiceProfilerWriterManager::PopAndInsert2DB(std::vector<DbBuffer *> &workingDbBuffers, std::set<DbBuffer *> &disableDbBuffers,
                                                  std::vector<DbBuffer *> &freeDbBuffers) {
    constexpr int MAX_POP_SIZE = 1000;
    int popCount = 0;
    for (DbBuffer *pbuffer : workingDbBuffers) {
        int leftPopSize = MAX_POP_SIZE;
        do {
            DbActivityMarker *pMarker = pbuffer->Pop();
            if (pMarker == nullptr) {
                break;
            }
            ServiceProfilerDbWriter::GetInstance().InsertMstxData(pMarker);
            free(pMarker);
            popCount++;
        } while (leftPopSize--);

        if (leftPopSize == MAX_POP_SIZE && disableDbBuffers.find(pbuffer) != disableDbBuffers.end()) {
            freeDbBuffers.push_back(pbuffer);
        }
    }
    return popCount;
}

ServiceProfilerThreadWriter::ServiceProfilerThreadWriter()
{
    pBuffer = ServiceProfilerWriterManager::GetInstance().Register(this);
}

ServiceProfilerThreadWriter::~ServiceProfilerThreadWriter()
{
    ServiceProfilerWriterManager::GetInstance().Unregister(this);
}

void ServiceProfilerThreadWriter::Insert(DbActivityMarker *activity)
{
    if (pBuffer) {
        pBuffer->Push(activity);
    }
}

void InsertTxData2Writer(DbActivityMarker *activity)
{
    thread_local ServiceProfilerThreadWriter writer;
    writer.Insert(activity);
}

void CloseTxData2Writer()
{
    ServiceProfilerWriterManager::GetInstance().Close();
}

void StartTxData2Writer(const std::string &outputPath)
{
    ServiceProfilerWriterManager::GetInstance().Start(outputPath);
}

}  // namespace msServiceProfiler