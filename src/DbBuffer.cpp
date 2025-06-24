/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

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
    auto *pNodeArray = (NodeDbActivityMarker *)malloc(PTR_ARRAY_PRE_SIZE * sizeof(NodeDbActivityMarker));
    memset(pNodeArray, 0, PTR_ARRAY_PRE_SIZE * sizeof(NodeDbActivityMarker));

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
        pHead_ = NewBuffer(pHead_, pNext);
    } else {
        pHead_ = pNext;
    }

    pHead_->pMarker = pMarker;
    SizeAdd();
    return;
}

void DbBuffer::Print()
{
    for (long long unsigned int i = 0; i < PTR_ARRAY_SIZE; ++i) {
        if (markerArray_[i] == nullptr) {
            continue;
        }
        for (long long unsigned int j = 0; j < PTR_ARRAY_PRE_SIZE; ++j) {
            auto *pInfo = &markerArray_[i][j];

            std::cout << std::hex << std::setw(10) << std::setfill('0') << pInfo << "(";
            std::cout << std::hex << std::setw(10) << std::setfill('0') << GetNext(pInfo) << " ";
            if (pInfo->pMarker == nullptr) {
                std::cout << std::dec << -1 << ") ";
            } else {
                std::cout << std::dec << std::setw(2) << std::setfill('0') << pInfo->pMarker->id << ") ";
            }
        }
        std::cout << std::dec << "\n";
    }
    std::cout << std::dec << "\n";
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

// // 全局缓冲区实例
// msServiceProfiler::DbBuffer dbBuffer;

// // 写线程函数
// void writerThread()
// {
//     int markerId = 0;
//     while (true) {
//         DbActivityMarker *pMarker = (DbActivityMarker *)malloc(sizeof(DbActivityMarker));
//         pMarker->id = markerId++;
//         dbBuffer.Push(pMarker);
//         if (markerId < 1000 || (markerId > 3000 && markerId < 6000)) {
//             std::this_thread::sleep_for(std::chrono::microseconds(3));  // 模拟写操作的延迟
//         } else if (markerId < 2700) {
//             std::this_thread::sleep_for(std::chrono::microseconds(13));  // 模拟写操作的延迟
//         } else {
//             std::this_thread::sleep_for(std::chrono::microseconds(1000));  // 模拟写操作的延迟
//         }
//     }
// }

// // 读线程函数
// void readerThread()
// {
//     uint64_t ori = 0;
//     while (true) {
//         DbActivityMarker *pMarker = dbBuffer.Pop();
//         auto size = dbBuffer.Size();
//         if (pMarker != nullptr) {
//             std::cout << "Read marker ID: " << pMarker->id << ' ' << size << std::endl;
//             if (pMarker->id != ori + 1) {
//                 std::cerr << "ERROR"
//                           << " " << pMarker->id << ' ' << ori << ' ' << size << std::endl;
//                 // dbBuffer.Print();
//             }
//             ori = pMarker->id;
//             free(pMarker);
//         }
//         std::this_thread::sleep_for(std::chrono::microseconds(10));  // 模拟读操作的延迟
//     }
// }

// int main()
// {
//     // 启动写线程
//     std::thread writer(writerThread);

//     // 启动读线程
//     std::thread reader(readerThread);

//     // 等待线程结束（实际上这两个线程是无限循环，这里仅作为示例）
//     writer.join();
//     reader.join();

//     return 0;
// }