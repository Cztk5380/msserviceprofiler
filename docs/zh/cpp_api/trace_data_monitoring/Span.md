# Span<a name="ZH-CN_TOPIC_0000002519080159"></a>

## AI处理器支持情况<a name="section13361171693320"></a>

>![](public_sys-resources/icon-note.gif) **说明：** 
>昇腾AI处理器与昇腾产品的对应关系，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|AI处理器类型|是否支持|
|--|:-:|
|Ascend 910C|×|
|Ascend 910B|√|
|Ascend 310B|×|
|Ascend 310P|√|
|Ascend 910|×|


>![](public_sys-resources/icon-notice.gif) **须知：** 
>针对Ascend 910B，当前仅支持该系列产品中的Atlas 800I A2 推理服务器。
>针对Ascend 310P，当前仅支持该系列产品中的Atlas 300I Duo 推理卡+Atlas 800 推理服务器（型号：3000）。

## 功能说明<a name="section12591713163317"></a>

创建一个跨度。

## 函数原型<a name="section1121883194711"></a>

```CPP
Span(const char* spanName, TraceContext& ctx, bool isSampled = true,const char* moduleName = nullptr, bool autoEnd = true)
```

## 参数说明<a name="section11506138144714"></a>

**表 1**  参数说明

|参数名|输入/输出|说明|
|--|--|--|
|spanName|输入|跨度名称。|
|ctx|输入|Trace上下文。|
|isSampled|输入|是否采样（默认true）。|
|moduleName|输入|模块名称（可选）。|
|autoEnd|输入|是否自动结束（默认true）。|


## 返回值说明<a name="section16621124213476"></a>

当前Trace的上下文信息。

