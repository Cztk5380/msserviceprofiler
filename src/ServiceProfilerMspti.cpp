/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <sys/stat.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <unistd.h>
#include <semaphore.h>
#include <utime.h>
#include <fcntl.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstring>
#include <climits>
#include <ctime>
#include <fstream>
#include <iostream>
#include <thread>
#include <vector>
#include <map>
#include <cmath>
#include <csignal>
#include <mutex>

#include "securec.h"

#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/ServiceProfilerMspti.h"

std::mutex g_mtx;

#define ALIGN_BUFFER(buffer, align)                                                 \
(((uintptr_t) (buffer) & ((align) - 1)) ? ((buffer) + (align) - ((uintptr_t) (buffer) & ((align) - 1))) : (buffer))

namespace msServiceProfiler {

    // 分割字符串并存入set 输入字符串格式为"xxxx;xxx;xxx"或"xxx;xxx;"均可
    static std::set<std::string> splitStringToSet(const std::string& str, char splitSymbol)
    {
        std::set<std::string> result;
        std::string token;

        for (char c : str) {
            if (c == splitSymbol) {
                if (!token.empty()) {       // 非空子串才插入
                    result.insert(token);
                    token.clear();          // 清空临时 token
                }
            } else {
                token += c;                 // 累积字符到临时 token
            }
        }

        // 处理最后一个子串（如果末尾没有分号）
        if (!token.empty()) {
            result.insert(token);
        }

        return result;
    }

    // 判断mspti上报的每条数据的名称是否在筛选目标中
    bool isNameMatch(std::set<std::string>& filterSet, const char* name)
    {
        if (!filterSet.empty()) {
            std::set<std::string>::iterator it;
            for (it=filterSet.begin(); it!=filterSet.end(); it++) {
                if (std::strstr(name, (*it).c_str()) != nullptr) {
                    return true;
                }
            }
            return false;
        }
        return true;
    }


    void ServiceProfilerMspti::insertApiData(msptiActivityApi* activity)
    {
        if (!inited || !activity || !stmtApi) {
            return;
        }

        if (!isNameMatch(filterApi, activity->name)) {
            return;
        }

        // mspti数据上报时 多线程之间存在抢占 需要使用线程锁防止数据踩踏
        g_mtx.lock();

        // 绑定参数
        int bind_index = 1;
        sqlite3_bind_text(stmtApi, bind_index++, activity->name, -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtApi, bind_index++, static_cast<int64_t>(activity->start));
        sqlite3_bind_int64(stmtApi, bind_index++, static_cast<int64_t>(activity->end));
        sqlite3_bind_int64(stmtApi, bind_index++, activity->pt.processId);
        sqlite3_bind_int64(stmtApi, bind_index++, activity->pt.threadId);
        sqlite3_bind_int64(stmtApi, bind_index++, static_cast<int64_t>(activity->correlationId));

        // 执行插入
        if (sqlite3_step(stmtApi) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s.", sqlite3_errmsg(db));
        }
        sqlite3_reset(stmtApi);

        // 解锁线程锁
        g_mtx.unlock();
    }

    void ServiceProfilerMspti::insertKernelData(msptiActivityKernel* activity)
    {
        if (!inited || !activity || !stmtKernel) {
            return;
        }

        if (!isNameMatch(filterKernel, activity->name)) {
            return;
        }

        g_mtx.lock();

        // 绑定参数
        int bind_index = 1;
        sqlite3_bind_text(stmtKernel, bind_index++, activity->type, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmtKernel, bind_index++, activity->name, -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtKernel, bind_index++, static_cast<int64_t>(activity->start));
        sqlite3_bind_int64(stmtKernel, bind_index++, static_cast<int64_t>(activity->end));
        sqlite3_bind_int64(stmtKernel, bind_index++, activity->ds.deviceId);
        sqlite3_bind_int64(stmtKernel, bind_index++, activity->ds.streamId);
        sqlite3_bind_int64(stmtKernel, bind_index++, static_cast<int64_t>(activity->correlationId));

        // 执行插入
        if (sqlite3_step(stmtKernel) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s.", sqlite3_errmsg(db));
        }
        sqlite3_reset(stmtKernel);
        g_mtx.unlock();
    }

    void ServiceProfilerMspti::insertCommData(msptiActivityHccl* activity)
    {
        if (!inited || !activity || !stmtComm) {
            return;
        }

        if (!isNameMatch(filterApi, activity->name)) {
            return;
        }

        g_mtx.lock();

        // 绑定参数
        int bind_index = 1;
        sqlite3_bind_text(stmtComm, bind_index++, activity->name, -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtComm, bind_index++, static_cast<int64_t>(activity->start));
        sqlite3_bind_int64(stmtComm, bind_index++, static_cast<int64_t>(activity->end));
        sqlite3_bind_int64(stmtComm, bind_index++, static_cast<int64_t>(activity->ds.deviceId));
        sqlite3_bind_int64(stmtComm, bind_index++, static_cast<int64_t>(activity->ds.streamId));
        sqlite3_bind_int64(stmtComm, bind_index++, static_cast<int64_t>(activity->bandWidth));
        sqlite3_bind_text(stmtComm, bind_index++, activity->commName, -1, SQLITE_STATIC);

        // 执行插入
        if (sqlite3_step(stmtComm) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s.", sqlite3_errmsg(db));
        }
        sqlite3_reset(stmtComm);

        g_mtx.unlock();
    }

    void ServiceProfilerMspti::insertMstxData(msptiActivityMarker* activity)
    {
        if (!inited || !activity || !stmtMstx) {
            return;
        }

        g_mtx.lock();

        // 绑定参数
        int bind_index = 1;
        if (activity->sourceKind == MSPTI_ACTIVITY_SOURCE_KIND_HOST) {
            sqlite3_bind_int64(stmtMstx, bind_index++, activity->objectId.pt.processId);
            sqlite3_bind_int64(stmtMstx, bind_index++, activity->objectId.pt.threadId);
        } else {
            sqlite3_bind_int64(stmtMstx, bind_index++, -1);
            sqlite3_bind_int64(stmtMstx, bind_index++, -1);
        }
        sqlite3_bind_int64(stmtMstx, bind_index++, activity->flag);
        sqlite3_bind_int64(stmtMstx, bind_index++, static_cast<int64_t>(activity->timestamp));
        
        sqlite3_bind_int64(stmtMstx, bind_index++, static_cast<int64_t>(activity->id));
        sqlite3_bind_int64(stmtMstx, bind_index++, activity->sourceKind);
        sqlite3_bind_text(stmtMstx, bind_index++, activity->name, -1, SQLITE_STATIC);

        // 执行插入
        if (sqlite3_step(stmtMstx) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s.", sqlite3_errmsg(db));
        }
        sqlite3_reset(stmtMstx);
        g_mtx.unlock();
    }


    void ServiceProfilerMspti::ServiceProfilerMspti::Init()
    {
        if (inited) {
            return;
        }

        PROF_LOGD("Initing ServiceFilerWriter.");

        // 打开数据库连接
        int rc = sqlite3_open(file_name.c_str(), &db);
        if (rc) {
            PROF_LOGE("Can't open database: %s.", sqlite3_errmsg(db));
            return;
        }

        createTable();

        inited = true;
        PROF_LOGD("Init ServiceProfilerFilerWriter Success.");
    }

    void ServiceProfilerMspti::InitFilter(std::string& apiFilter, std::string& kernelFilter)
    {
        filterApi = splitStringToSet(apiFilter, SPLIT_SYMBOL);
        filterKernel = splitStringToSet(kernelFilter, SPLIT_SYMBOL);
    }

    void ServiceProfilerMspti::InitOutputPath(std::string& outputPath)
    {
        file_name = outputPath + "ascend_service_profiler_" + std::to_string(getpid()) + ".db";
        PROF_LOGD("set mspti output path: %s", file_name.c_str());
    }

    void ServiceProfilerMspti::createTable()
    {
        createMstxTable();
        createApiTable();
        createKernelTable();
        createCommTable();
    }

    void ServiceProfilerMspti::createMstxTable()
    {
        char* errMsg = nullptr;

        const char* sqlCreateKindMstx =
            "CREATE TABLE IF NOT EXISTS Mstx ("
            "pid INTEGER,"
            "tid INTEGER,"
            "event_type TEXT,"
            "timestamp INTEGER,"
            "mark_id INTEGER,"
            "domain TEXT,"
            "message TEXT);";
        const char* sqlInsertKindMstx =
            "INSERT INTO Mstx "
            "(pid, tid, event_type, timestamp, mark_id, domain, message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);";

        if (sqlite3_exec(db, sqlCreateKindMstx, nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE("sqlCreateKindMstx SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db, sqlInsertKindMstx, -1, &stmtMstx, nullptr) != SQLITE_OK) {
            PROF_LOGE("sqlInsertKindMstx SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
    }

    void ServiceProfilerMspti::createApiTable()
    {
        char* errMsg = nullptr;

        const char* sqlCreateKindApi =
            "CREATE TABLE IF NOT EXISTS Api ("
            "name TEXT,"
            "start INTEGER,"
            "end INTEGER,"
            "processId INTEGER,"
            "threadId INTEGER,"
            "correlationId INTEGER);";

        const char* sqlInsertKindApi =
            "INSERT INTO Api "
            "(name, start, end, processId, threadId, correlationId) "
            "VALUES (?, ?, ?, ?, ?, ?);";
        if (sqlite3_exec(db, sqlCreateKindApi, nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE("sqlCreateKindApi SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db, sqlInsertKindApi, -1, &stmtApi, nullptr) != SQLITE_OK) {
            PROF_LOGE("sqlInsertKindApi SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
    }
    
    void ServiceProfilerMspti::createKernelTable()
    {
        char* errMsg = nullptr;

        const char* sqlCreateKindKernel =
            "CREATE TABLE IF NOT EXISTS Kernel ("
            "type TEXT,"
            "name TEXT,"
            "start INTEGER,"
            "end INTEGER,"
            "deviceId INTEGER,"
            "streamId INTEGER,"
            "correlationId INTEGER);";

        const char* sqlInsertKindKernel =
            "INSERT INTO Kernel "
            "(type, name, start, end, deviceId, streamId, correlationId) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);";
        if (sqlite3_exec(db, sqlCreateKindKernel, nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE("sqlCreateKindKernel SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db, sqlInsertKindKernel, -1, &stmtKernel, nullptr) != SQLITE_OK) {
            PROF_LOGE("sqlInsertKindKernel SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
    }

    void ServiceProfilerMspti::createCommTable()
    {
        char* errMsg = nullptr;

        const char* sqlCreateKindComm =
            "CREATE TABLE IF NOT EXISTS Comm ("
            "name TEXT,"
            "start INTEGER,"
            "end INTEGER,"
            "deviceId INTEGER,"
            "streamId INTEGER,"
            "bandWidth INTEGER,"
            "commName TEXT);";

        const char* sqlInsertKindComm =
            "INSERT INTO Comm "
            "(name, start, end, deviceId, streamId, bandWidth, commName) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);";
        if (sqlite3_exec(db, sqlCreateKindComm, nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE("sqlCreateKindComm SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db, sqlInsertKindComm, -1, &stmtComm, nullptr) != SQLITE_OK) {
            PROF_LOGE("sqlInsertKindComm SQL error: %s", errMsg);
            sqlite3_free(errMsg);
        }
    }

    void ServiceProfilerMspti::Close()
    {
        // 释放资源
        if (inited) {
            sqlite3_finalize(stmtApi);
            sqlite3_finalize(stmtKernel);
            sqlite3_finalize(stmtComm);
            sqlite3_finalize(stmtMstx);

            sqlite3_close(db);
            inited = false;
        }
    }

    void ServiceProfilerMspti::AddWorkingThreadNum()
    {
        workingThreadNum = workingThreadNum + 1;
    }

    void ServiceProfilerMspti::PopWorkingThreadNum()
    {
        if (workingThreadNum > 0) {
            workingThreadNum = workingThreadNum - 1;
        } else {
            PROF_LOGW("No thread is working, pop working thread failed.");
        }
    }

    void ServiceProfilerMspti::ResetWorkingThreadNum()
    {
        workingThreadNum = 0;
    }

    bool ServiceProfilerMspti::GetWorkingStatus()
    {
        return (workingThreadNum > 0);
    }


    static void ShowApiInfo(msptiActivityApi* api)
    {
        if (!api) {
            PROF_LOGD("ShowApiInfo failed, nullptr api.");
            return;
        }
        ServiceProfilerMspti::GetInstance().insertApiData(api);
    }

    static void ShowKernelInfo(msptiActivityKernel* kernel)
    {
        if (!kernel) {
            PROF_LOGD("ShowKernelInfo failed, nullptr kernel.");
            return;
        }
        ServiceProfilerMspti::GetInstance().insertKernelData(kernel);
    }

    static void ShowCommInfo(msptiActivityHccl* activity)
    {
        if (!activity) {
            return;
        }
        ServiceProfilerMspti::GetInstance().insertCommData(activity);
    }

    static void ShowMstxInfo(msptiActivityMarker* activity)
    {
        if (!activity) {
            return;
        }
        ServiceProfilerMspti::GetInstance().insertMstxData(activity);
    }

    // MSPTI
    void UserBufferComplete(uint8_t *buffer, size_t size, size_t validSize)
    {
        PROF_LOGD("UserBuffer complete, processing buffer data.");
        ServiceProfilerMspti::GetInstance().AddWorkingThreadNum();
        // profiler manager会在每个进程上创建 而host上的进程暂时不会有mspti数据上报 因此在这个位置初始化 防止创建host上的空db
        ServiceProfilerMspti::GetInstance().Init();
        if (validSize <= 0) {
            PROF_LOGE("Invalid validSize.");
            return;
        }
        msptiActivity *pRecord = NULL;
        msptiResult status = MSPTI_SUCCESS;
        do {
            status = msptiActivityGetNextRecord(buffer, validSize, &pRecord);
            if (status == MSPTI_SUCCESS) {
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_API) {
                    msptiActivityApi* activity = reinterpret_cast<msptiActivityApi*>(pRecord);
                    ShowApiInfo(activity);
                }
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_KERNEL) {
                    msptiActivityKernel* activity = reinterpret_cast<msptiActivityKernel*>(pRecord);
                    ShowKernelInfo(activity);
                }
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_HCCL) {
                    msptiActivityHccl* activity = reinterpret_cast<msptiActivityHccl*>(pRecord);
                    ShowCommInfo(activity);
                }
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_MARKER) {
                    msptiActivityMarker* activity = reinterpret_cast<msptiActivityMarker*>(pRecord);
                    ShowMstxInfo(activity);
                }
            } else if (status == MSPTI_ERROR_MAX_LIMIT_REACHED) {
                break;
            } else {
                PROF_LOGD("unexpected status: %d", status);
                break;
            }
        } while (1);

        free(buffer);
        ServiceProfilerMspti::GetInstance().PopWorkingThreadNum();
    }

    // MSPTI
    void UserBufferRequest(uint8_t **buffer, size_t *size, size_t *maxNumRecords)
    {
        constexpr uint32_t SIZE = 1 * ONE_K * ONE_K;
        uint8_t *pBuffer = (uint8_t *) malloc(SIZE + ALIGN_SIZE);
        *buffer = ALIGN_BUFFER(pBuffer, ALIGN_SIZE);
        *size = 1 * ONE_K * ONE_K;
        *maxNumRecords = 0;
    }

    int InitMspti(std::string& profPath_, msptiSubscriberHandle& subscriber)
    {
        // 创建mspti订阅者
        auto ret = msptiSubscribe(&subscriber, nullptr, nullptr);
        if (ret == MSPTI_SUCCESS) {
            PROF_LOGD("Mspti subscribe success.");
        } else if (ret == MSPTI_ERROR_MULTIPLE_SUBSCRIBERS_NOT_SUPPORTED) {
                PROF_LOGW("Mspti subscribe failed. Multiple subscribe is not allowed.");
        } else {
            if (ret == MSPTI_ERROR_INNER) {
                PROF_LOGD("Mspti subscribe failed. Inner error.");
            } else if (ret == MSPTI_ERROR_INVALID_PARAMETER) {
                PROF_LOGD("Mspti subscribe failed. Invalid parameter.");
            } else {
                PROF_LOGD("Mspti subscribe failed. Unknown error, error code %d", ret);
            }
            return ret;
        }

        // 注册空buffer申请回调函数 以及buffer满时的数据处理回调函数
        ret = msptiActivityRegisterCallbacks(UserBufferRequest, UserBufferComplete);
        if (ret == MSPTI_SUCCESS) {
            PROF_LOGD("Mspti register callbacks success.");
        } else {
            if (ret == MSPTI_ERROR_INVALID_PARAMETER) {
                PROF_LOGD("Mspti register callbacks failed. Invalid parameter.");
            } else {
                PROF_LOGD("Mspti register callbacks failed. Unknown error, error code %d.", ret);
            }
            return ret;
        }
        ServiceProfilerMspti::GetInstance().InitOutputPath(profPath_);
        return 0;
    }

    void InitMsptiActivity(bool msptiEnable_)
    {
        msptiResult ret;
        if (msptiEnable_) {
            ret = msptiActivityEnable(MSPTI_ACTIVITY_KIND_API);
            if (ret != MSPTI_SUCCESS) {
                PROF_LOGE("Mspti enable api activity failed.");
            }
            ret = msptiActivityEnable(MSPTI_ACTIVITY_KIND_KERNEL);
            if (ret != MSPTI_SUCCESS) {
                PROF_LOGE("Mspti enable kernel activity failed.");
            }
            ret = msptiActivityEnable(MSPTI_ACTIVITY_KIND_HCCL);
            if (ret != MSPTI_SUCCESS) {
                PROF_LOGE("Mspti enable Comm activity failed.");
            }
        }

        ret = msptiActivityEnable(MSPTI_ACTIVITY_KIND_MARKER);
        if (ret != MSPTI_SUCCESS) {
            PROF_LOGE("Mspti enable mstx activity failed.");
        }
    }

    void InitMsptiFilter(std::string& apiFilter, std::string& kernelFilter)
    {
        ServiceProfilerMspti::GetInstance().InitFilter(apiFilter, kernelFilter);
    }

    void UninitMspti(msptiSubscriberHandle& subscriber)
    {
        PROF_LOGD("Unit Mspti.");
        auto ret = msptiActivityFlushAll(1);
        if (ret != MSPTI_SUCCESS) {
            PROF_LOGE("Mspti Flush All failed.");
        }

        ret = msptiUnsubscribe(subscriber);
        if (ret != MSPTI_SUCCESS) {
            PROF_LOGE("Mspti Unsubscribe failed.");
        }
        ServiceProfilerMspti::GetInstance().ResetWorkingThreadNum();
        ServiceProfilerMspti::GetInstance().Close();
    }

    void FlushBufferByTime()
    {
        bool workingStatus = ServiceProfilerMspti::GetInstance().GetWorkingStatus();
        if (!workingStatus) {
            PROF_LOGD("No mspti flush working thread running for period, automaticaly flush all.");
            auto ret = msptiActivityFlushAll(1);
            if (ret != MSPTI_SUCCESS) {
                PROF_LOGE("Mspti Flush All failed.");
            }
        }
    }
}  // namespace msServiceProfiler
