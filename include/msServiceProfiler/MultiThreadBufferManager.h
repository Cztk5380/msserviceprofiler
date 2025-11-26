/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 */

#ifndef MS_SERVICE_PROFILER_MULTITHREADBUFFERMANAGER_H
#define MS_SERVICE_PROFILER_MULTITHREADBUFFERMANAGER_H

#include <functional>
#include <string>
#include <map>
#include <set>
#include <vector>
#include <mutex>
#include <thread>
#include <cmath>
#include <algorithm>
#include <memory>
#include <sqlite3.h>

#include "Log.h"
#include "DbBuffer.h"

namespace msServiceProfiler {
constexpr size_t MAX_POP_SIZE = 2000;

template <typename T>
class MultiThreadBufferManager {
public:
    MultiThreadBufferManager(std::function<void(std::unique_ptr<T>)> popFunc, std::function<void()> batchEndFunc)
        : popFunc_(popFunc), batchEndFunc_(batchEndFunc)
    {
        this->thread_ = std::thread(&MultiThreadBufferManager::DumpThread, this);
        pPopMarkerBuffer = std::make_unique<std::unique_ptr<T>[]>(MAX_POP_SIZE);
    };

    ~MultiThreadBufferManager()
    {
        PROF_LOGD("Multi Thread Buffer Manager free");
        threadExitFlag_ = true;
        if (this->thread_.joinable()) {
            this->thread_.join();
        }
        PROF_LOGD("Multi Thread Buffer Manager free thread over");
        std::lock_guard<std::mutex> lock(mtx_);
        lifeEndFlag_ = true;
        workingDbBuffers_.clear();
        disableDbBuffers_.clear();
    };

    void DumpThread()
    {
        constexpr int SUITABLE_DUMP_SIZE = 1000;
        constexpr int MAX_WAIT_US = 50000;  // 50ms
        constexpr int MIN_WAIT_US = 50;     // 50us
        int waitUs = MIN_WAIT_US;
        std::set<std::shared_ptr<DbBuffer<T>>> disableDbBuffers;
        std::vector<std::shared_ptr<DbBuffer<T>>> workingDbBuffers;
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
            std::vector<DbBuffer<T> *> freeDbBuffers;
            auto popCount = popFromBuffers(workingDbBuffers, disableDbBuffers, freeDbBuffers);

            // 更科学的从min和max之间转换
            double diff = std::max(std::min((SUITABLE_DUMP_SIZE - popCount) / 400.0, 2.5), -2.5);
            int diff_exp = static_cast<int>(exp(diff));  // 因为 diff 限制了范围，所以 exp diff 也不会超过 int 的范围
            waitUs = std::min(std::max(waitUs * diff_exp, MIN_WAIT_US), MAX_WAIT_US);  // 维持在写入1000条每次左右
            {
                std::lock_guard<std::mutex> lock(mtx_);

                for (auto *pBuffer : freeDbBuffers) {
                    std::shared_ptr<DbBuffer<T>> pTempBuffer(pBuffer, [](DbBuffer<T> *) {});
                    workingDbBuffers_.erase(
                        std::remove(workingDbBuffers_.begin(), workingDbBuffers_.end(), pTempBuffer),
                        workingDbBuffers_.end());
                    disableDbBuffers_.erase(pTempBuffer);
                }
                workingDbBuffers = workingDbBuffers_;
                disableDbBuffers = disableDbBuffers_;
            }
            if (popCount > 0) {
                PROF_LOGD("buffer thread pop %d items", popCount);
            }
        }
    }

    int popFromBuffers(const std::vector<std::shared_ptr<DbBuffer<T>>> &workingDbBuffers,
        std::set<std::shared_ptr<DbBuffer<T>>> &disableDbBuffers, std::vector<DbBuffer<T> *> &freeDbBuffers)
    {
        int popCount = 0;
        std::unique_ptr<T> *pMarkers = pPopMarkerBuffer.get();
        // pop
        for (const auto &pBuffer : workingDbBuffers) {
            size_t popSize = pBuffer->Pop(MAX_POP_SIZE, pMarkers);
            for (size_t i = 0; i < popSize; ++i) {
                if (pMarkers[i] == nullptr) {
                    continue;
                }

                popFunc_(std::move(pMarkers[i]));
                pMarkers[i] = nullptr;
            }
            popCount += static_cast<int>(popSize);  // 数值不会太大，直接加没关系

            if (popSize == 0 && disableDbBuffers.find(pBuffer) != disableDbBuffers.end()) {
                freeDbBuffers.push_back(pBuffer.get());
            }
        }
        batchEndFunc_();
        return popCount;
    }

    // 只有register 和 unregister 是多线程竞争，其他都是通过 DBBuffer 过来的 Executor 执行，保证顺序，且不需要保护。
    std::shared_ptr<DbBuffer<T>> Register(uintptr_t pThreadIns)
    {
        std::lock_guard<std::mutex> lock(mtx_);
        auto pBuffer = std::make_shared<DbBuffer<T>>();
        mapBuffer_[pThreadIns] = pBuffer;
        workingDbBuffers_.push_back(pBuffer);
        return pBuffer;
    }

    void Unregister(uintptr_t pThreadIns)
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

private:
    std::mutex mtx_;
    std::thread thread_;
    bool lifeEndFlag_ = false;
    bool threadExitFlag_ = false;

    std::map<uintptr_t, std::shared_ptr<DbBuffer<T>>> mapBuffer_{};
    std::set<std::shared_ptr<DbBuffer<T>>> disableDbBuffers_{};
    std::vector<std::shared_ptr<DbBuffer<T>>> workingDbBuffers_{};

    std::unique_ptr<std::unique_ptr<T>[]> pPopMarkerBuffer{};

    std::function<void(std::unique_ptr<T>)> popFunc_;
    std::function<void()> batchEndFunc_;
};
}  // namespace msServiceProfiler

#endif  // MS_SERVICE_PROFILER_MULTITHREADBUFFERMANAGER_H
