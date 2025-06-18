/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2025-5-15
 */
#include "mspti/mspti.h"
namespace UTHelper {
msptiResult g_utStatusMsptiActivityRegisterCallbacks = msptiResult::MSPTI_SUCCESS;
msptiResult g_utStatusMsptiActivityEnable = msptiResult::MSPTI_SUCCESS;
msptiResult g_utStatusMsptiActivityFlushAll = msptiResult::MSPTI_SUCCESS;
msptiResult g_utStatusMsptiSubscribe = msptiResult::MSPTI_SUCCESS;
msptiResult g_utStatusMsptiUnsubscribe = msptiResult::MSPTI_SUCCESS;
}

using namespace UTHelper;

msptiResult msptiActivityRegisterCallbacks(bufferRequestFunctionPtr, bufferCompleteFunctionPtr)
{
    return g_utStatusMsptiActivityRegisterCallbacks;
}

msptiResult msptiActivityEnable(int kind)
{
    return g_utStatusMsptiActivityEnable;
}

msptiResult msptiActivityGetNextRecord(uint8_t *buffer, size_t validBufferSizeBytes, msptiActivity **record)
{
    // for ut
    thread_local uint8_t *localBuffer = nullptr;
    if (buffer == localBuffer) {
        localBuffer = nullptr;
        return MSPTI_ERROR_MAX_LIMIT_REACHED;
    }
    localBuffer = buffer;
    *record = reinterpret_cast<msptiActivity *>(buffer);
    if (buffer == nullptr) {
        return MSPTI_ERROR_INVALID_PARAMETER;
    } else if (validBufferSizeBytes < sizeof(msptiActivity)) {
        return MSPTI_ERROR_MAX_LIMIT_REACHED;
    } else {
        return MSPTI_SUCCESS;
    }
}

msptiResult msptiActivityFlushAll(int kind)
{
    return g_utStatusMsptiActivityFlushAll;
}

msptiResult msptiSubscribe(msptiSubscriberHandle *subscriber, int *callback, int *userdata)
{
    return g_utStatusMsptiSubscribe;
}

msptiResult msptiUnsubscribe(msptiSubscriberHandle subscriber)
{
    return g_utStatusMsptiUnsubscribe;
}