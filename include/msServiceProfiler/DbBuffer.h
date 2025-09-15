/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */
#ifndef SERVICE_PROFILER_DB_BUFFER_H
#define SERVICE_PROFILER_DB_BUFFER_H

#include <atomic>
#include <thread>
#include <iomanip>
#include "msServiceProfiler/Log.h"

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
#define MS_SERVICE_INLINE_FLAG [[gnu::noinline]]
#else
#define MS_SERVICE_INLINE_FLAG inline
#endif

namespace msServiceProfiler {

constexpr long long unsigned int PTR_ARRAY_SIZE = 128;
constexpr long long unsigned int PTR_ARRAY_PRE_SIZE = 128;

template <typename T>
class DbBuffer {
    struct NodeDbActivityMarker {
        std::unique_ptr<T> pMarkerData = nullptr;
        NodeDbActivityMarker *pNext = nullptr;
    };

public:
    DbBuffer() = default;
    ~DbBuffer()
    {
        for (auto &array : markerArray_) {
            if (array != nullptr) {
                delete[] array;
                array = nullptr;
            }
        }
    };

    std::unique_ptr<T> Push(std::unique_ptr<T> pMarkerData)
    {
#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
        pushCount_++;
#endif
        if (pMarkerData == nullptr) {
            return pMarkerData;
        }
        const auto size = Size();

        auto *pNext = GetNext(pHead_);

        if (size + 1 >= BufferSize()) {  // +1 是因为不要影响到 pTail_， 离开一点距离
            if (bufferIndex_ > PTR_ARRAY_SIZE - 1) {
                LOG_ONCE_E("no more new buffer. max size is: %lu", size);  // LCOV_EXCL_LINE
                return pMarkerData;
            }
            auto *pBuffer = NewBuffer(pHead_, pNext);
            if (pBuffer != nullptr) {
                pHead_ = pBuffer;
            } else {
                LOG_ONCE_E("no more new buffer. now size is: %lu", size);  // LCOV_EXCL_LINE
                return pMarkerData;
            }
        } else {
            pHead_ = pNext;
        }

        // 检查 pHead_ 是否为空
        if (pHead_ != nullptr) {
            pHead_->pMarkerData = std::move(pMarkerData);
            SizeAdd();
        } else {
            LOG_ONCE_E("pHead_ is null, cannot proceed.");  // LCOV_EXCL_LINE
            return nullptr;
        }

        return nullptr;
    };

    size_t Pop(const size_t maxPopSize, std::unique_ptr<T> *popDataArray)
    {
        const auto size = Size();
        if (size == 0) {
            return 0;
        }
        size_t popCntThisTime = 0;

        while (popCntThisTime < std::min(maxPopSize, size)) {
            if (pTail_ == nullptr) {
                pTail_ = markerArray_[0];
            } else {
                pTail_ = GetNext(pTail_);
            }
            popDataArray[popCntThisTime] = std::move(pTail_->pMarkerData);
            popCntThisTime++;
            SizeSub();
        }

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
        maxCountInBuffer_ = std::max(maxCountInBuffer_, size);
        popCount_ += popCntThisTime;
#endif

        return popCntThisTime;
    };

    size_t Size() const
    {
        return Size_.load(std::memory_order_relaxed);
    };

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
    [[gnu::noinline]] size_t PopCnt() const
    {
        return popCount_;
    };
    [[gnu::noinline]] size_t PushCnt() const
    {
        return pushCount_;
    };
    [[gnu::noinline]] size_t MaxCntInBuffer() const
    {
        return maxCountInBuffer_;
    };
#endif

private:
    size_t BufferSize() const
    {
        return bufferSize_;
    };

    size_t SizeAdd()
    {
        return Size_.fetch_add(1, std::memory_order_release);
    };

    size_t SizeSub()
    {
        return Size_.fetch_sub(1, std::memory_order_acquire);
    };

    NodeDbActivityMarker *NewBuffer(NodeDbActivityMarker *pThis, NodeDbActivityMarker *pNext)
    {
        auto *pNodeArray = new (std::nothrow) NodeDbActivityMarker[PTR_ARRAY_PRE_SIZE];
        if (pNodeArray == nullptr) {
            return nullptr;
        }

        if (pNext == nullptr) {
            pNodeArray[PTR_ARRAY_PRE_SIZE - 1].pNext = pNodeArray;
        } else {
            pNodeArray[PTR_ARRAY_PRE_SIZE - 1].pNext = pNext;
            pThis->pNext = pNodeArray;
        }
        markerArray_[bufferIndex_] = pNodeArray;
        bufferIndex_++;
        bufferSize_ += PTR_ARRAY_PRE_SIZE;
        return pNodeArray;
    };

    static NodeDbActivityMarker *GetNext(NodeDbActivityMarker *pNode)
    {
        if (pNode == nullptr) {
            return nullptr;
        }

        NodeDbActivityMarker *pNext = pNode->pNext;
        if (pNext == nullptr) {
            pNext = ++pNode;
        }
        return pNext;
    };

private:
    NodeDbActivityMarker *markerArray_[PTR_ARRAY_SIZE] = {nullptr};
    size_t bufferSize_ = 0;
    size_t bufferIndex_ = 0;
    NodeDbActivityMarker *pHead_ = nullptr;
    NodeDbActivityMarker *pTail_ = nullptr;
    std::atomic<size_t> Size_{};
#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
    size_t pushCount_ = 0;
    size_t popCount_ = 0;
    size_t maxCountInBuffer_ = 0;
#endif
};
}  // namespace msServiceProfiler

#endif  // SERVICE_PROFILER_DB_BUFFER_H
