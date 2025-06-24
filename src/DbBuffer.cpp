/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */
#include "securec.h"
#include "msServiceProfiler/DbBuffer.h"

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

void DbBuffer::Push(DbActivityMarker *pMarker)
{
    auto size = Size();

    auto *pNext = GetNext(pHead_);

    if (size + 1 >= BufferSize()) {
        if (bufferIndex_ + 1 >= PTR_ARRAY_SIZE) {
            return;
        }
        auto *pBuffer = NewBuffer(pHead_, pNext);
        if (pBuffer != nullptr) {
            pHead_ = pBuffer;
        } else {
            return;
        }
    } else {
        pHead_ = pNext;
    }

    pHead_->pMarker = pMarker;
    SizeAdd();
    return;
}

DbActivityMarker *DbBuffer::Pop()
{
    auto size = Size();
    if (size == 0) {
        return nullptr;
    }
    if (pTail_ == nullptr) {
        pTail_ = markerArray_[0];
    } else {
        pTail_ = GetNext(pTail_);
    }
    auto pMarker = pTail_->pMarker;
    pTail_->pMarker = nullptr;
    SizeSub();
    return pMarker;
}

DbBuffer::~DbBuffer()
{
    for (long long unsigned int i = 0; i < PTR_ARRAY_SIZE; ++i) {
        if (markerArray_[i] != nullptr) {
            delete markerArray_[i];
            markerArray_[i] = nullptr;
        }
    }
}
}  // namespace msServiceProfiler
