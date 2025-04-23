#ifndef PROFILER_LOG_H
#define PROFILER_LOG_H

#include <cstdio>
#include <unistd.h> // for getpid()

// 日志级别枚举
enum ProfLogLevel {
    PROF_LOG_NONE = 0,
    PROF_LOG_ERROR,
    PROF_LOG_WARNING,
    PROF_LOG_INFO,
    PROF_LOG_DEBUG
};

// 初始化日志系统
void prof_log_init();

// 获取当前日志级别
ProfLogLevel prof_log_get_level();

// 设置日志级别
void prof_log_set_level(ProfLogLevel level);

// 日志宏定义
#define PROF_LOGD(...) \
    do { \
        if (prof_log_get_level() >= PROF_LOG_DEBUG) { \
            printf("[msservice_profiler] [PID:%d] [DEBUG] [%s:%d] ", getpid(), __func__, __LINE__); \
            printf(__VA_ARGS__); \
            printf("\n"); \
        } \
    } while (0)

#define PROF_LOGI(...) \
    do { \
        if (prof_log_get_level() >= PROF_LOG_INFO) { \
            printf("[msservice_profiler] [PID:%d] [INFO] [%s:%d] ", getpid(), __func__, __LINE__); \
            printf(__VA_ARGS__); \
            printf("\n"); \
        } \
    } while (0)

#define PROF_LOGW(...) \
    do { \
        if (prof_log_get_level() >= PROF_LOG_WARNING) { \
            printf("[msservice_profiler] [PID:%d] [WARNING] [%s:%d] ", getpid(), __func__, __LINE__); \
            printf(__VA_ARGS__); \
            printf("\n"); \
        } \
    } while (0)

#define PROF_LOGE(...) \
    do { \
        if (prof_log_get_level() >= PROF_LOG_ERROR) { \
            printf("[msservice_profiler] [PID:%d] [ERROR] [%s:%d] ", getpid(), __func__, __LINE__); \
            printf(__VA_ARGS__); \
            printf("\n"); \
        } \
    } while (0)

#define LOG_ONCE_D(...) \
    do { \
        static bool logged_##__LINE__ = false; \
        if (!logged_##__LINE__) { \
            PROF_LOGD(__VA_ARGS__); \
            logged_##__LINE__ = true; \
        } \
    } while(0)

#define LOG_ONCE_W(...) \
    do { \
        static bool logged_##__LINE__ = false; \
        if (!logged_##__LINE__) { \
            PROF_LOGW(__VA_ARGS__); \
            logged_##__LINE__ = true; \
        } \
    } while(0)

#define LOG_ONCE_E(...) \
    do { \
        static bool logged_##__LINE__ = false; \
        if (!logged_##__LINE__) { \
            PROF_LOGE(__VA_ARGS__); \
            logged_##__LINE__ = true; \
        } \
    } while(0)

#endif // PROFILER_LOG_H
