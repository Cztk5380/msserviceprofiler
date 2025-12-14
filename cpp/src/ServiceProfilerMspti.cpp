/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

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
#include <fstream>
#include <thread>
#include <vector>
#include <cmath>
#include <csignal>
#include <mutex>
#include <memory>

#include "securec.h"
#include "msServiceProfiler/Utils.h"
#include "msServiceProfiler/Log.h"
#include "msServiceProfiler/ServiceProfilerDbWriter.h"
#include "msServiceProfiler/DBExecutor/DbExecutorMsptiApiData.h"
#include "msServiceProfiler/DBExecutor/DbExecutorMsptikernelData.h"
#include "msServiceProfiler/DBExecutor/DbExecutorMsptiCommData.h"
#include "msServiceProfiler/DBExecutor/DbExecutorMsptiMstxData.h"
#include "msServiceProfiler/ServiceProfilerMspti.h"

std::mutex g_mtx;

namespace msServiceProfiler {
    class BufferPool {
        struct BufferInfo {
            uint8_t* pBuffer;
            size_t size;
        };
    public:
        static BufferPool& GetBufferPool()
        {
            static BufferPool bufferPool;
            return bufferPool;
        }
        BufferInfo GetBuffer()
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (pBufferPool.empty()) {
                return BufferInfo{nullptr, 0};
            }
            BufferInfo bufferInfo = pBufferPool.back();
            pBufferPool.pop_back();
            return bufferInfo;
        };
        void Clear(const bool close = false)
        {
            std::lock_guard<std::mutex> lock(mutex_);
            closeFlag = close;
            for (auto& pBuffer : pBufferPool) {
                free(pBuffer.pBuffer);
                pBuffer.pBuffer = nullptr;
            };
            pBufferPool.clear();
        };
        void RecycleBuffer(uint8_t* buffer, const size_t size)
        {
            if (buffer == nullptr || size == 0) {
                return;
            }
            std::lock_guard<std::mutex> lock(mutex_);
            if (closeFlag) {
                free(buffer);
                buffer = nullptr;
                return;
            }
            pBufferPool.push_back(BufferInfo{buffer, size});
        };
        ~BufferPool()
        {
            Clear(true);
        }
    private:
        bool closeFlag = false;
        std::mutex mutex_;
        std::vector<BufferInfo> pBufferPool;
    };

    // 判断mspti上报的每条数据的名称是否在筛选目标中
    bool ServiceProfilerMspti::IsNameMatch(const std::set<std::string>& filterSet, const char* name)
    {
        if (name == nullptr) {
            return false;
        }
        if (!filterSet.empty()) {
            for (auto it = filterSet.begin(); it!=filterSet.end(); ++it) {
                if (std::strstr(name, it->c_str()) != nullptr) {
                    return true;
                }
            }
            return false;
        }
        return true;
    }

    void ServiceProfilerMspti::Init()
    {
        if (inited) {
            return;
        }

        PROF_LOGD("Initing ServiceFilerWriter.");
        std::string outputDir = outputDir_;
        auto executor = std::make_unique<DbFuncExec>(
            [outputDir](ServiceProfilerDbWriter &writer, sqlite3 *) -> void { writer.StartDump(outputDir); }, PRIORITY_START_PROF);
        msServiceProfiler::InsertExecutor2Writer<DBFile::MSPTI>(std::move(executor));
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
        outputDir_ = outputPath;
        PROF_LOGD("set mspti output path: %s", outputDir_.c_str());  // LCOV_EXCL_LINE
    }

    void ServiceProfilerMspti::Close()
    {
        // 释放资源
        if (inited) {
            inited = false;
        }
        auto executor =
            std::make_unique<DbFuncExec>([](ServiceProfilerDbWriter &writer, sqlite3 *) -> void { writer.StopDump(); }, PRIORITY_STOP_PROF);
        msServiceProfiler::InsertExecutor2Writer<DBFile::MSPTI>(std::move(executor));
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
        if (!ServiceProfilerMspti::GetInstance().ApiNameMatch(api->name)) {
            return;
        }
        auto executor = std::make_unique<DbExecutor<MSPTI_API_INSERT_STMT>>(*api);
        msServiceProfiler::InsertExecutor2Writer<DBFile::MSPTI>(std::move(executor));
    }

    static void ShowKernelInfo(msptiActivityKernel* kernel)
    {
        if (!kernel) {
            PROF_LOGD("ShowKernelInfo failed, nullptr kernel.");  // LCOV_EXCL_LINE
            return;
        }
        if (!ServiceProfilerMspti::GetInstance().KernelNameMatch(kernel->name)) {
            return;
        }
        auto executor = std::make_unique<DbExecutor<MSPTI_KERNEL_INSERT_STMT>>(*kernel);
        msServiceProfiler::InsertExecutor2Writer<DBFile::MSPTI>(std::move(executor));
    }

    static void ShowCommunicationInfo(msptiActivityCommunication* activity)
    {
        if (!activity) {
            return;
        }
        auto executor = std::make_unique<DbExecutor<MSPTI_COMMUNICATION_INSERT_STMT>>(*activity);
        msServiceProfiler::InsertExecutor2Writer<DBFile::MSPTI>(std::move(executor));
    }

    static void ShowMstxInfo(msptiActivityMarker* activity)
    {
        if (!activity) {
            return;
        }

        auto executor = std::make_unique<DbExecutor<MSPTI_MSTX_INSERT_STMT>>(*activity);
        msServiceProfiler::InsertExecutor2Writer<DBFile::MSPTI>(std::move(executor));
    }

    // MSPTI
    void UserBufferComplete(uint8_t *buffer, size_t size, size_t validSize)
    {
        PROF_LOGD("UserBuffer complete, processing buffer data.");  // LCOV_EXCL_LINE
        ServiceProfilerMspti::GetInstance().AddWorkingThreadNum();
        // profiler manager会在每个进程上创建 而host上的进程暂时不会有mspti数据上报 因此在这个位置初始化 防止创建host上的空db
        ServiceProfilerMspti::GetInstance().Init();
        int recv_size = 0;
        if (validSize < 1) {
            PROF_LOGE("Invalid validSize.");  // LCOV_EXCL_LINE
            return;
        }
        msptiActivity *pRecord = nullptr;
        msptiResult status = MSPTI_SUCCESS;
        do {
            status = msptiActivityGetNextRecord(buffer, validSize, &pRecord);
            ++recv_size;
            if (status == MSPTI_SUCCESS) {
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_API) {
                    auto* activity = reinterpret_cast<msptiActivityApi*>(pRecord);
                    ShowApiInfo(activity);
                }
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_KERNEL) {
                    auto* activity = reinterpret_cast<msptiActivityKernel*>(pRecord);
                    ShowKernelInfo(activity);
                }
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_COMMUNICATION) {
                    auto* activity = reinterpret_cast<msptiActivityCommunication*>(pRecord);
                    ShowCommunicationInfo(activity);
                }
                if (pRecord->kind == MSPTI_ACTIVITY_KIND_MARKER) {
                    auto* activity = reinterpret_cast<msptiActivityMarker*>(pRecord);
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
            BufferPool::GetBufferPool().RecycleBuffer(buffer, size);
        }
        ServiceProfilerMspti::GetInstance().PopWorkingThreadNum();

        PROF_LOGD("MSPTI buffer size is : %lu, item size: %d", size, recv_size);  // LCOV_EXCL_LINE
    }

    void UserBufferClear()
    {
        BufferPool::GetBufferPool().Clear();
    }

    // MSPTI
    void UserBufferRequest(uint8_t **buffer, size_t *size, size_t *maxNumRecords)
    {
        *buffer = nullptr;
        *size = 0;
        *maxNumRecords = 0;

        auto cacheBuffer = BufferPool::GetBufferPool().GetBuffer();
        if (cacheBuffer.pBuffer != nullptr) {
            *buffer = cacheBuffer.pBuffer;
            *size = cacheBuffer.size;

            PROF_LOGD("MSPTI get cached buffer size is : %lu", *size);  // LCOV_EXCL_LINE
            return;
        }
        constexpr size_t bufferSize = 1 * ONE_K * ONE_K;
        constexpr size_t alignment = ALIGN_SIZE;
        // 多分配空间确保能对齐
        auto *pBuffer = static_cast<uint8_t*>(malloc(bufferSize + alignment));
        if (!pBuffer) {
            PROF_LOGE("Buffer request failed.");
            return;
        }
        // 使用 std::align 计算对齐地址
        void* alignedPtr = pBuffer;
        size_t space = bufferSize + alignment;
        if (!std::align(alignment, bufferSize, alignedPtr, space)) {
            free(pBuffer);
            pBuffer = nullptr;
            *buffer = nullptr;
            PROF_LOGE("Buffer request failed.");
            return;
        }
        *buffer = static_cast<uint8_t*>(alignedPtr);
        *size = bufferSize;
        PROF_LOGD("MSPTI get new buffer size is : %lu", *size);  // LCOV_EXCL_LINE
    }

    int InitMspti(const std::string& profPath_, msptiSubscriberHandle& subscriber)
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
        MsUtils::FailAutoFree autoFree;
        autoFree.AddFreeFunction([&subscriber]() {
                if (msptiUnsubscribe(subscriber) != MSPTI_SUCCESS) {
                    PROF_LOGE("Mspti Unsubscribe failed.");  // LCOV_EXCL_LINE
                }
            },
            "auto call unsubscribe after subscribe when init failed.");

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

        autoFree.SetSuccess();
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
            auto ret = msptiActivityFlushAll(1);
            if (ret != MSPTI_SUCCESS) {
                PROF_LOGE("Mspti Flush All failed.");  // LCOV_EXCL_LINE
            }
        }
    }

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
    void CallShowApiInfo(msptiActivityApi* api)
    {
        ShowApiInfo(api);
    };
    void CallShowKernelInfo(msptiActivityKernel* api)
    {
        ShowKernelInfo(api);
    };
    void CallShowCommunicationInfo(msptiActivityCommunication* api)
    {
        ShowCommunicationInfo(api);
    };
    void CallShowMstxInfo(msptiActivityMarker* api)
    {
        ShowMstxInfo(api);
    };
#endif

}  // namespace msServiceProfiler
