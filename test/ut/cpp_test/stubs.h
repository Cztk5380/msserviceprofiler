/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
 */

#include <gmock/gmock.h>

using SpanHandle = uint64_t;

class StubFunc {
public:
    virtual void* dlopen(const char* filename, int flag) = 0;
    virtual void* dlsym(void* handle, const char* symbol) = 0;
    virtual int access(const char *__name, int __type) = 0;
    virtual char *realpath(const char *__name, char *__resolved) = 0;
    virtual int stat(const char *__file, struct stat *__buf) = 0;
    virtual int shm_open(const char *__name, int __oflag, mode_t __mode) = 0;
    virtual int ftruncate(int __fd, __off_t __length) = 0;

    virtual SpanHandle StartSpanWithName(const char* name) = 0;
    virtual void MarkSpanAttr(const char* msg, SpanHandle spanHandle) = 0;
    virtual void EndSpan(SpanHandle spanHandle) = 0;
    virtual void MarkEvent(const char* msg) = 0;
    virtual bool IsEnable(uint32_t level) = 0;
};

class MockStubFunc : public StubFunc {
public:
    MOCK_METHOD2(dlopen, void*(const char*, int));
    MOCK_METHOD2(dlsym, void*(void*, const char*));
    MOCK_METHOD2(access, int(const char*, int));
    MOCK_METHOD2(realpath, char*(const char*, char*));
    MOCK_METHOD2(stat, int(const char*, struct stat*));
    MOCK_METHOD3(shm_open, int(const char*, int, mode_t));
    MOCK_METHOD2(ftruncate, int(int, __off_t));

    MOCK_METHOD1(StartSpanWithName, SpanHandle(const char*));
    MOCK_METHOD2(MarkSpanAttr, void(const char*, SpanHandle));
    MOCK_METHOD1(EndSpan, void(SpanHandle));
    MOCK_METHOD1(MarkEvent, void(const char*));
    MOCK_METHOD1(IsEnable, bool(uint32_t));
};
