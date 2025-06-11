/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2025-5-15
 */
#include "mspti/mspti.h"

msptiResult msptiActivityRegisterCallbacks(bufferRequestFunctionPtr, bufferCompleteFunctionPtr)
{
    return MSPTI_SUCCESS;
}

msptiResult msptiActivityEnable(int kind)
{
    return MSPTI_SUCCESS;
}

msptiResult msptiActivityGetNextRecord(uint8_t *buffer, size_t validBufferSizeBytes, msptiActivity **record)
{
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
    return MSPTI_SUCCESS;
}

msptiResult msptiSubscribe(msptiSubscriberHandle *subscriber, int *callback, int *userdata)
{
    return MSPTI_SUCCESS;
}

msptiResult msptiUnsubscribe(msptiSubscriberHandle subscriber)
{
    return MSPTI_SUCCESS;
}