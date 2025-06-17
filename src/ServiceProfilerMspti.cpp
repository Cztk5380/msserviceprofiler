/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <sys/stat.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <unistd.h>
#include <semaphore.h>
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
#include "msServiceProfiler/Utils.h"
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/ServiceProfilerMspti.h"

std::mutex g_mtx;

namespace msServiceProfiler {
    // 判断mspti上报的每条数据的名称是否在筛选目标中
    bool IsNameMatch(std::set<std::string>& filterSet, const char* name)
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

    void ServiceProfilerMspti::InsertApiData(msptiActivityApi* activity)
    {
        if (!inited || !activity || !stmtApi) {
            return;
        }

        if (!IsNameMatch(filterApi, activity->name)) {
            return;
        }

        // mspti数据上报时 多线程之间存在抢占 需要使用线程锁防止数据踩踏
        std::lock_guard<std::mutex> lg(g_mtx);

        // 绑定参数
        int bindIndex = 1;
        sqlite3_bind_text(stmtApi, bindIndex++, activity->name, -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtApi, bindIndex++, static_cast<int64_t>(activity->start));
        sqlite3_bind_int64(stmtApi, bindIndex++, static_cast<int64_t>(activity->end));
        sqlite3_bind_int64(stmtApi, bindIndex++, activity->pt.processId);
        sqlite3_bind_int64(stmtApi, bindIndex++, activity->pt.threadId);
        sqlite3_bind_int64(stmtApi, bindIndex++, static_cast<int64_t>(activity->correlationId));

        // 执行插入
        if (sqlite3_step(stmtApi) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s.", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtApi);
    }

    void ServiceProfilerMspti::InsertKernelData(msptiActivityKernel* activity)
    {
        if (!inited || !activity || !stmtKernel) {
            return;
        }

        if (!IsNameMatch(filterKernel, activity->name)) {
            return;
        }

        std::lock_guard<std::mutex> lg(g_mtx);

        // 绑定参数
        int bindIndex = 1;
        sqlite3_bind_text(stmtKernel, bindIndex++, activity->type, -1, SQLITE_STATIC);
        sqlite3_bind_text(stmtKernel, bindIndex++, activity->name, -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtKernel, bindIndex++, static_cast<int64_t>(activity->start));
        sqlite3_bind_int64(stmtKernel, bindIndex++, static_cast<int64_t>(activity->end));
        sqlite3_bind_int64(stmtKernel, bindIndex++, activity->ds.deviceId);
        sqlite3_bind_int64(stmtKernel, bindIndex++, activity->ds.streamId);
        sqlite3_bind_int64(stmtKernel, bindIndex++, static_cast<int64_t>(activity->correlationId));

        // 执行插入
        if (sqlite3_step(stmtKernel) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s.", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtKernel);
    }

    void ServiceProfilerMspti::InsertCommunicationData(msptiActivityCommunication* activity)
    {
        if (!inited || !activity || !stmtCommunication) {
            return;
        }

        std::lock_guard<std::mutex> lg(g_mtx);

        // 绑定参数
        int bindIndex = 1;
        sqlite3_bind_text(stmtCommunication, bindIndex++, activity->name, -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(activity->start));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(activity->end));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(activity->ds.deviceId));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(activity->ds.streamId));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(activity->count));
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(activity->dataType));
        sqlite3_bind_text(stmtCommunication, bindIndex++, activity->commName, -1, SQLITE_STATIC);
        sqlite3_bind_int64(stmtCommunication, bindIndex++, static_cast<int64_t>(activity->correlationId));

        // 执行插入
        if (sqlite3_step(stmtCommunication) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s.", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtCommunication);
    }

    void ServiceProfilerMspti::InsertMstxData(msptiActivityMarker* activity)
    {
        if (!inited || !activity || !stmtMstx) {
            return;
        }

        std::lock_guard<std::mutex> lg(g_mtx);

        // 绑定参数
        int bindIndex = 1;
        if (activity->sourceKind == MSPTI_ACTIVITY_SOURCE_KIND_HOST) {
            sqlite3_bind_int64(stmtMstx, bindIndex++, activity->objectId.pt.processId);
            sqlite3_bind_int64(stmtMstx, bindIndex++, activity->objectId.pt.threadId);
        } else {
            sqlite3_bind_int64(stmtMstx, bindIndex++, -1);
            sqlite3_bind_int64(stmtMstx, bindIndex++, -1);
        }
        sqlite3_bind_int64(stmtMstx, bindIndex++, activity->flag);
        sqlite3_bind_int64(stmtMstx, bindIndex++, static_cast<int64_t>(activity->timestamp));
        
        sqlite3_bind_int64(stmtMstx, bindIndex++, static_cast<int64_t>(activity->id));
        sqlite3_bind_int64(stmtMstx, bindIndex++, activity->sourceKind);
        sqlite3_bind_text(stmtMstx, bindIndex++, activity->name, -1, SQLITE_STATIC);

        // 执行插入
        if (sqlite3_step(stmtMstx) != SQLITE_DONE) {
            PROF_LOGE("Execution failed: %s.", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
        }
        sqlite3_reset(stmtMstx);
    }


    void ServiceProfilerMspti::ServiceProfilerMspti::Init()
    {
        if (inited) {
            return;
        }

        PROF_LOGD("Initing ServiceFilerWriter.");
        mode_t new_umask = 0137;  // ascend_service_profiler_*.db的权限设置为640
        mode_t old_umask = umask(new_umask);

        // 打开数据库连接
        int rc = sqlite3_open(file_name.c_str(), &db);
        if (rc != 0) {
            PROF_LOGE("Can't open database: %s.", sqlite3_errmsg(db));  // LCOV_EXCL_LINE
            return;
        }
        umask(old_umask);
        CreateTable();

        inited = true;
        PROF_LOGD("Init ServiceProfilerFilerWriter Success.");  // LCOV_EXCL_LINE
    }

    void ServiceProfilerMspti::InitFilter(const std::string& apiFilter, const std::string& kernelFilter)
    {
        filterApi = MsUtils::SplitStringToSet(apiFilter, SPLIT_SYMBOL);
        filterKernel = MsUtils::SplitStringToSet(kernelFilter, SPLIT_SYMBOL);
    }

    void ServiceProfilerMspti::InitOutputPath(const std::string& outputPath)
    {
        file_name = outputPath + "ascend_service_profiler_" + std::to_string(getpid()) + ".db";
        PROF_LOGD("set mspti output path: %s", file_name.c_str());  // LCOV_EXCL_LINE
    }

    void ServiceProfilerMspti::CreateTable()
    {
        CreateMstxTable();
        CreateApiTable();
        CreateKernelTable();
        CreateCommunicationTable();
    }

    void ServiceProfilerMspti::CreateMstxTable()
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
            PROF_LOGE("sqlCreateKindMstx SQL error: %s", errMsg);  // LCOV_EXCL_LINE
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db, sqlInsertKindMstx, -1, &stmtMstx, nullptr) != SQLITE_OK) {
            PROF_LOGE("sqlInsertKindMstx SQL error: %s", errMsg);  // LCOV_EXCL_LINE
            sqlite3_free(errMsg);
        }
    }

    void ServiceProfilerMspti::CreateApiTable()
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
            PROF_LOGE("sqlCreateKindApi SQL error: %s", errMsg);  // LCOV_EXCL_LINE
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db, sqlInsertKindApi, -1, &stmtApi, nullptr) != SQLITE_OK) {
            PROF_LOGE("sqlInsertKindApi SQL error: %s", errMsg);  // LCOV_EXCL_LINE
            sqlite3_free(errMsg);
        }
    }
    
    void ServiceProfilerMspti::CreateKernelTable()
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
            PROF_LOGE("sqlCreateKindKernel SQL error: %s", errMsg);  // LCOV_EXCL_LINE
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db, sqlInsertKindKernel, -1, &stmtKernel, nullptr) != SQLITE_OK) {
            PROF_LOGE("sqlInsertKindKernel SQL error: %s", errMsg);  // LCOV_EXCL_LINE
            sqlite3_free(errMsg);
        }
    }

    void ServiceProfilerMspti::CreateCommunicationTable()
    {
        char* errMsg = nullptr;

        const char* sqlCreateKindCommunication =
            "CREATE TABLE IF NOT EXISTS Communication ("
            "name TEXT,"
            "start INTEGER,"
            "end INTEGER,"
            "deviceId INTEGER,"
            "streamId INTEGER,"
            "dataCount INTEGER,"
            "dataType INTEGER,"
            "commGroupName TEXT,"
            "correlationId INTEGER);";

        const char* sqlInsertKindCommunication =
            "INSERT INTO Communication "
            "(name, start, end, deviceId, streamId, dataCount, dataType, commGroupName, correlationId) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);";
        if (sqlite3_exec(db, sqlCreateKindCommunication, nullptr, nullptr, &errMsg) != SQLITE_OK) {
            PROF_LOGE("sqlCreateKindCommunication SQL error: %s", errMsg);  // LCOV_EXCL_LINE
            sqlite3_free(errMsg);
        }
        if (sqlite3_prepare_v2(db, sqlInsertKindCommunication, -1, &stmtCommunication, nullptr) != SQLITE_OK) {
            PROF_LOGE("sqlInsertKindCommunication SQL error: %s", errMsg);  // LCOV_EXCL_LINE
            sqlite3_free(errMsg);
        }
    }

    void ServiceProfilerMspti::Close()
    {
        // 释放资源
        if (inited) {
            sqlite3_finalize(stmtApi);
            sqlite3_finalize(stmtKernel);
            sqlite3_finalize(stmtCommunication);
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
            PROF_LOGW("No thread is working, pop working thread failed.");  // LCOV_EXCL_LINE
        }
    }

    void ServiceProfilerMspti::ResetWorkingThreadNum()
    {
        workingThreadNum = 0;
    }

    bool ServiceProfilerMspti::GetWorkingStatus() const
    {
        return (workingThreadNum > 0);
    }

    static void ShowApiInfo(msptiActivityApi* api)
    {
        if (!api) {
            PROF_LOGD("ShowApiInfo failed, nullptr api.");  // LCOV_EXCL_LINE
            return;
        }
        ServiceProfilerMspti::GetInstance().InsertApiData(api);
    }

    static void ShowKernelInfo(msptiActivityKernel* kernel)
    {
        if (!kernel) {
            PROF_LOGD("ShowKernelInfo failed, nullptr kernel.");  // LCOV_EXCL_LINE
            return;
        }
        ServiceProfilerMspti::GetInstance().InsertKernelData(kernel);
    }

    static void ShowCommunicationInfo(msptiActivityCommunication* activity)
    {
        if (!activity) {
            return;
        }
        ServiceProfilerMspti::GetInstance().InsertCommunicationData(activity);
    }

    static void ShowMstxInfo(msptiActivityMarker* activity)
    {
        if (!activity) {
            return;
        }
        ServiceProfilerMspti::GetInstance().InsertMstxData(activity);
    }

    // MSPTI
    void UserBufferComplete(uint8_t *buffer, size_t size, size_t validSize)
    {
        PROF_LOGD("UserBuffer complete, processing buffer data.");  // LCOV_EXCL_LINE
        ServiceProfilerMspti::GetInstance().AddWorkingThreadNum();
        // profiler manager会在每个进程上创建 而host上的进程暂时不会有mspti数据上报 因此在这个位置初始化 防止创建host上的空db
        ServiceProfilerMspti::GetInstance().Init();
        if (validSize < 1) {
            PROF_LOGE("Invalid validSize.");  // LCOV_EXCL_LINE
            return;
        }
        msptiActivity *pRecord = nullptr;
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
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_COMMUNICATION) {
                    msptiActivityCommunication* activity = reinterpret_cast<msptiActivityCommunication*>(pRecord);
                    ShowCommunicationInfo(activity);
                }
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_MARKER) {
                    msptiActivityMarker* activity = reinterpret_cast<msptiActivityMarker*>(pRecord);
                    ShowMstxInfo(activity);
                }
            } else if (status == MSPTI_ERROR_MAX_LIMIT_REACHED) {
                break;
            } else {
                PROF_LOGD("unexpected status: %d", status);  // LCOV_EXCL_LINE
                break;
            }
        } while (true);
        
        if (buffer) {
            free(buffer);
        }
        ServiceProfilerMspti::GetInstance().PopWorkingThreadNum();
    }

    // MSPTI
    void UserBufferRequest(uint8_t **buffer, size_t *size, size_t *maxNumRecords)
    {
        uint8_t *pBuffer = static_cast<uint8_t *>(malloc(1 * ONE_K * ONE_K + ALIGN_SIZE));
        *buffer = (((reinterpret_cast<uintptr_t>(pBuffer) & (ALIGN_SIZE - 1)) != 0)
                ? (pBuffer + (ALIGN_SIZE - (reinterpret_cast<uintptr_t>(pBuffer) & (ALIGN_SIZE - 1))))
                : pBuffer);
        *size = 1 * ONE_K * ONE_K;
        *maxNumRecords = 0;
    }

    int InitMspti(std::string& profPath_, msptiSubscriberHandle& subscriber)
    {
        // 创建mspti订阅者
        auto ret = msptiSubscribe(&subscriber, nullptr, nullptr);
        if (ret == MSPTI_SUCCESS) {
            PROF_LOGD("Mspti subscribe success.");  // LCOV_EXCL_LINE
        } else if (ret == MSPTI_ERROR_MULTIPLE_SUBSCRIBERS_NOT_SUPPORTED) {
                PROF_LOGW("Mspti subscribe failed. Multiple subscribe is not allowed.");  // LCOV_EXCL_LINE
        } else {
            if (ret == MSPTI_ERROR_INNER) {
                PROF_LOGD("Mspti subscribe failed. Inner error.");  // LCOV_EXCL_LINE
            } else if (ret == MSPTI_ERROR_INVALID_PARAMETER) {
                PROF_LOGD("Mspti subscribe failed. Invalid parameter.");  // LCOV_EXCL_LINE
            } else {
                PROF_LOGD("Mspti subscribe failed. Unknown error, error code %d", ret);  // LCOV_EXCL_LINE
            }
            return ret;
        }

        // 注册空buffer申请回调函数 以及buffer满时的数据处理回调函数
        ret = msptiActivityRegisterCallbacks(UserBufferRequest, UserBufferComplete);
        if (ret == MSPTI_SUCCESS) {
            PROF_LOGD("Mspti register callbacks success.");  // LCOV_EXCL_LINE
        } else {
            if (ret == MSPTI_ERROR_INVALID_PARAMETER) {
                PROF_LOGD("Mspti register callbacks failed. Invalid parameter.");  // LCOV_EXCL_LINE
            } else {
                PROF_LOGD("Mspti register callbacks failed. Unknown error, error code %d.", ret);  // LCOV_EXCL_LINE
            }
            return ret;
        }
        ServiceProfilerMspti::GetInstance().InitOutputPath(profPath_);
        return 0;
    }

    void InitMsptiActivity(bool msptiEnable)
    {
        msptiResult ret;
        if (msptiEnable) {
            ret = msptiActivityEnable(MSPTI_ACTIVITY_KIND_API);
            if (ret != MSPTI_SUCCESS) {
                PROF_LOGE("Mspti enable api activity failed.");  // LCOV_EXCL_LINE
            }
            ret = msptiActivityEnable(MSPTI_ACTIVITY_KIND_KERNEL);
            if (ret != MSPTI_SUCCESS) {
                PROF_LOGE("Mspti enable kernel activity failed.");  // LCOV_EXCL_LINE
            }
            ret = msptiActivityEnable(MSPTI_ACTIVITY_KIND_COMMUNICATION);
            if (ret != MSPTI_SUCCESS) {
                PROF_LOGE("Mspti enable Communication activity failed.");  // LCOV_EXCL_LINE
            }
        }

        ret = msptiActivityEnable(MSPTI_ACTIVITY_KIND_MARKER);
        if (ret != MSPTI_SUCCESS) {
            PROF_LOGE("Mspti enable mstx activity failed.");  // LCOV_EXCL_LINE
        }
    }

    void InitMsptiFilter(const std::string& apiFilter, const std::string& kernelFilter)
    {
        ServiceProfilerMspti::GetInstance().InitFilter(apiFilter, kernelFilter);
    }

    void UninitMspti(msptiSubscriberHandle& subscriber)
    {
        PROF_LOGD("Unit Mspti.");  // LCOV_EXCL_LINE
        auto ret = msptiActivityFlushAll(1);
        if (ret != MSPTI_SUCCESS) {
            PROF_LOGE("Mspti Flush All failed.");  // LCOV_EXCL_LINE
        }

        ret = msptiUnsubscribe(subscriber);
        if (ret != MSPTI_SUCCESS) {
            PROF_LOGE("Mspti Unsubscribe failed.");  // LCOV_EXCL_LINE
        }
        ServiceProfilerMspti::GetInstance().ResetWorkingThreadNum();
        ServiceProfilerMspti::GetInstance().Close();
    }

    void FlushBufferByTime()
    {
        bool workingStatus = ServiceProfilerMspti::GetInstance().GetWorkingStatus();
        if (!workingStatus) {
            PROF_LOGD("No mspti flush working thread running for period, automaticaly flush all.");  // LCOV_EXCL_LINE
            auto ret = msptiActivityFlushAll(1);
            if (ret != MSPTI_SUCCESS) {
                PROF_LOGE("Mspti Flush All failed.");  // LCOV_EXCL_LINE
            }
        }
    }
}  // namespace msServiceProfiler
