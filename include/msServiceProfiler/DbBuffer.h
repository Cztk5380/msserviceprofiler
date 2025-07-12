/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */
#ifndef SERVICEPROFILERDBBUFFER_H
#define SERVICEPROFILERDBBUFFER_H

#include <atomic>
#include <thread>
#include <iostream>
#include <cstring>
#include <iomanip>
#include <type_traits>

#include "ServiceProfilerDbWriter.h"

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
#define MS_SERVICE_INLINE_FLAG [[gnu::noinline]]
#else
#define MS_SERVICE_INLINE_FLAG inline
#endif

namespace msServiceProfiler {

template <typename T>
constexpr int GetTypeIndex()
{
    if (std::is_same<T, DbActivityMarker>::value) {
        return 1;
    } else if (std::is_same<T, DbActivityMeta>::value) {
        return 2;
    } else {
        return 0;
    }
}
class NodeMarkerData {
public:
    virtual int GetType() = 0;
    virtual bool IsNull() = 0;
    virtual ~NodeMarkerData() = default;
};

template <typename T>
class NodeMarkerDataPtr : public NodeMarkerData {
public:
    NodeMarkerDataPtr(std::unique_ptr<T> dataPtr) : ptr_(std::move(dataPtr))
    {}
    int constexpr GetType() override
    {
        constexpr auto index = GetTypeIndex<T>();
        return index;
    }
    std::unique_ptr<T> MovePtr()
    {
        return std::move(ptr_);
    }
    bool IsNull() override
    {
        return ptr_ == nullptr;
    }

private:
    std::unique_ptr<T> ptr_;
};

using NodeDbActivityMarker = struct NODE_MARKER {
    std::unique_ptr<NodeMarkerData> pMarkerData = nullptr;
    NODE_MARKER *pNext = nullptr;
};

constexpr long long unsigned int PTR_ARRAY_SIZE = 128;
constexpr long long unsigned int PTR_ARRAY_PRE_SIZE = 128;

class DbBuffer {
public:
    MS_SERVICE_INLINE_FLAG DbBuffer(){};
    ~DbBuffer();
    std::unique_ptr<NodeMarkerData> Push(std::unique_ptr<NodeMarkerData> pMarker);
    size_t Pop(size_t maxPopSize, std::unique_ptr<NodeMarkerData> *popDataArray);
    size_t Size();

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
    size_t BufferSize();
    size_t SizeAdd();
    size_t SizeSub();
    NodeDbActivityMarker *NewBuffer(NodeDbActivityMarker *pThis, NodeDbActivityMarker *pNext);
    NodeDbActivityMarker *GetNext(NodeDbActivityMarker *pNode);

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

#endif  // SERVICEPROFILERDBBUFFER_H
