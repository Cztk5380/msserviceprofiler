# Attach<a name="ZH-CN_TOPIC_0000002487000272"></a>

## AI处理器支持情况<a name="section13361171693320"></a>

>![](public_sys-resources/icon-note.gif) **说明：** 
>昇腾AI处理器与昇腾产品的对应关系，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|AI处理器类型|是否支持|
|--|:-:|
|Ascend 910C|x|
|Ascend 910B|√|
|Ascend 310B|x|
|Ascend 310P|√|
|Ascend 910|x|


>![](public_sys-resources/icon-notice.gif) **须知：** 
>针对Ascend 910B，当前仅支持该系列产品中的Atlas 800I A2 推理产品。
>针对Ascend 310P，当前仅支持该系列产品中的Atlas 300I Duo 推理卡+Atlas 800 推理服务器（型号：3000）。

## 功能说明<a name="section12591713163317"></a>

附加Trace信息到当前上下文。

## 函数原型<a name="section1121883194711"></a>

```CPP
size_t Attach(const TraceId traceId, const SpanId spanId, const bool isSample = true)
```

## 参数说明<a name="section11506138144714"></a>

**表 1**  参数说明

|参数名|输入/输出|说明|
|--|--|--|
|traceId|输入|Trace ID。|
|spanId|输入|跨度ID。|
|isSample|输入|是否采样（默认true）|


## 返回值说明<a name="section16621124213476"></a>

返回上下文索引，作为[Unattach](Unattach.md)的调用参数。

