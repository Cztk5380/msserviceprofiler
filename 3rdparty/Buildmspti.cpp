/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2024. All rights reserved.
 * Description: wrapper header
 * Author: Huawei Technologies Co., Ltd.
 * Create: 2024-12-16
 */
#include "mspti/mspti.h"

msptiResult msptiActivityRegisterCallbacks(void (*func1(uint8_t, size_t, size_t)), void (*func2(uint8_t, size_t, size_t)))
{
    return 0;
}

msptiResult msptiActivityEnable(int kind)
{
    return 0;
}

msptiResult msptiActivityGetNextRecord(unit8_t *buffer, size_t validBufferSizeBytes, msptiActivity **record)
{
    return 0;
}

msptiResult msptiActivityFlushAll(int kind)
{
    return 0;
}

msptiResult msptiSubscribe(int subscriber, int callback, int userdata)
{
    return 0;
}