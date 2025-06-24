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

namespace msServiceProfiler {

using NodeDbActivityMarker = struct NODE_MARKER_DB {
    DbActivityMarker *pMarker;
    NODE_MARKER_DB *pNext;
};

constexpr long long unsigned int PTR_ARRAY_SIZE = 128;
constexpr long long unsigned int PTR_ARRAY_PRE_SIZE = 128;

class DbBuffer {
public:
    DbBuffer(){};
    void Push(DbActivityMarker *pMarker);
    DbActivityMarker *Pop();
    void Print();
    ~DbBuffer();

private:
    size_t BufferSize();
    size_t Size();
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
    std::atomic<size_t> Size_;
};
}  // namespace msServiceProfiler

#endif  // SERVICEPROFILERDBBUFFER_H
