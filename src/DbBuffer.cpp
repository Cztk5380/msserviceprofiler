/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */
#include "securec.h"
#include "msServiceProfiler/DbBuffer.h"
#include "msServiceProfiler/Log.h"

namespace msServiceProfiler {

size_t DbBuffer::BufferSize()
{
    return bufferSize_;
}

size_t DbBuffer::Size()
{
    return Size_.load(std::memory_order_relaxed);
}

size_t DbBuffer::SizeAdd()
{
    return Size_.fetch_add(1, std::memory_order_release);
}

size_t DbBuffer::SizeSub()
{
    return Size_.fetch_sub(1, std::memory_order_acquire);
}

NodeDbActivityMarker *DbBuffer::NewBuffer(NodeDbActivityMarker *pThis, NodeDbActivityMarker *pNext)
{
    auto bufferSize = PTR_ARRAY_PRE_SIZE * sizeof(NodeDbActivityMarker);
    auto *pNodeArray = (NodeDbActivityMarker *)malloc(bufferSize);
    if (pNodeArray == nullptr) {
        return nullptr;
    }
    memset_s(pNodeArray, bufferSize, 0, bufferSize);

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
}

NodeDbActivityMarker *DbBuffer::GetNext(NodeDbActivityMarker *pNode)
{
    if (pNode == nullptr) {
        return nullptr;
    }

    NodeDbActivityMarker *pNext = pNode->pNext;
    if (pNext == nullptr) {
        pNext = ++pNode;
    }
    return pNext;
}

bool DbBuffer::Push(DbActivityMarker *pMarker)
{
#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
    pushCount_++;
#endif
    if (pMarker == nullptr) {
        return false;
    }
    auto size = Size();

    auto *pNext = GetNext(pHead_);

    if (size + 1 >= BufferSize()) {  // +1 是因为不要影响到 pTail_， 离开一点距离
        if (bufferIndex_ > PTR_ARRAY_SIZE - 1) {
            LOG_ONCE_E("no more new buffer. max size is: %lu", size);  // LCOV_EXCL_LINE
            return false;
        }
        auto *pBuffer = NewBuffer(pHead_, pNext);
        if (pBuffer != nullptr) {
            pHead_ = pBuffer;
        } else {
            LOG_ONCE_E("no more new buffer. now size is: %lu", size);  // LCOV_EXCL_LINE
            return false;
        }
    } else {
        pHead_ = pNext;
    }

    pHead_->pMarker = pMarker;
    SizeAdd();
    return true;
}

size_t DbBuffer::Pop(size_t maxPopSize, DbActivityMarkerPtr *popBuffer)
{
    auto size = Size();
    if (size == 0) {
        return 0;
    }
    size_t popCntThisTime = 0;

    for (; popCntThisTime < std::min(maxPopSize, size);) {
        if (pTail_ == nullptr) {
            pTail_ = markerArray_[0];
        } else {
            pTail_ = GetNext(pTail_);
        }
        auto *pMarker = pTail_->pMarker;
        pTail_->pMarker = nullptr;
        popBuffer[popCntThisTime] = pMarker;
        popCntThisTime++;
        SizeSub();
    }

#ifdef ENABLE_SERVICE_PROF_UNIT_TEST
    maxCountInBuffer_ = std::max(maxCountInBuffer_, size);
    popCount_ += popCntThisTime;
#endif

    return popCntThisTime;
}

DbBuffer::~DbBuffer()
{
    constexpr size_t MAX_POP_SIZE = 2000;
    DbActivityMarkerPtr pMarkers[MAX_POP_SIZE] = {nullptr};
    size_t popSize = 0;
    do {
        size_t popSize = Pop(MAX_POP_SIZE, pMarkers);
        for (size_t i = 0; i < popSize; ++i) {
            if (pMarkers[i] != nullptr) {
                delete pMarkers[i];
                pMarkers[i] = nullptr;
            }
        }
    } while (popSize > 0);
    for (long long unsigned int i = 0; i < PTR_ARRAY_SIZE; ++i) {
        if (markerArray_[i] != nullptr) {
            free(markerArray_[i]);
            markerArray_[i] = nullptr;
        }
    }
}
}  // namespace msServiceProfiler
