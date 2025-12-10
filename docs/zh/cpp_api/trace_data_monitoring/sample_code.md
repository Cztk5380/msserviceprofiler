# 示例代码<a name="ZH-CN_TOPIC_0000002519876529"></a>

以下是关键步骤的代码示例，不可以直接拷贝编译运行，仅供参考。

```CPP
// 设置全局资源属性
if (msServiceProfiler::Tracer::IsEnable()) {
    msServiceProfiler::TraceContext::addResAttribute("service.name", "my-service");
    msServiceProfiler::TraceContext::addResAttribute("service.version", "1.0.0");
}
auto& ctx = msServiceProfiler::TraceContext::GetTraceCtx();
size_t indexHeader = ctx.ExtractAndAttach(traceParentHeader, b3Header);
size_t index = ctx.Attach(TraceId{1, 1}, SpanId{1}, true);  // Span 会自动Attach，一般不需要主动调用该函数
// 创建跨度
auto span = msServiceProfiler::Tracer::StartSpanAsActive("MyOperation", "MyModule");
// 设置属性
span.SetAttribute("key", "value")
    .SetStatus(true, "Operation completed successfully");
span.End();
ctx.Unattach(index);
ctx.Unattach(indexHeader);
```

