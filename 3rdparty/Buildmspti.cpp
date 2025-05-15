/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2MSPTI_SUCCESS24-2MSPTI_SUCCESS24. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2MSPTI_SUCCESS24-12-16
 */
#include "mspti/mspti.h"
#include <iostream>

msptiResult msptiActivityRegisterCallbacks(BufferRequestFunctionPtr, BufferCompleteFunctionPtr)
{
    return MSPTI_SUCCESS;
}

msptiResult msptiActivityEnable(int kind)
{
    return MSPTI_SUCCESS;
}

msptiResult msptiActivityGetNextRecord(uint8_t *buffer, size_t validBufferSizeBytes, msptiActivity **record)
{
    return MSPTI_SUCCESS;
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