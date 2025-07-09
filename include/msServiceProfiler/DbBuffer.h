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

#include "ServiceProfilerDbWriter.h"

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
#define MS_SERVICE_INLINE_FLAG [[gnu::noinline]]
#else
#define MS_SERVICE_INLINE_FLAG inline
#endif

namespace msServiceProfiler {

using NodeDbActivityMarker = struct NODE_MARKER_DB {
    DbActivityMarker *pMarker;
    NODE_MARKER_DB *pNext;
};

constexpr long long unsigned int PTR_ARRAY_SIZE = 128;
constexpr long long unsigned int PTR_ARRAY_PRE_SIZE = 128;

class DbBuffer {
public:
    MS_SERVICE_INLINE_FLAG DbBuffer(){};
    ~DbBuffer();
    bool Push(DbActivityMarker *pMarker);
    size_t Pop(size_t maxPopSize, DbActivityMarkerPtr *popBuffer);
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
