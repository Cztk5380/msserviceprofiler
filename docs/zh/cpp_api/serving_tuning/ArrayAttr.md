# ArrayAttr<a name="ZH-CN_TOPIC_0000002149395906"></a>

## AI处理器支持情况<a name="section8178181118225"></a>

>![](public_sys-resources/icon-note.gif) **说明：** 
>AI处理器与昇腾产品的对应关系，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

|AI处理器类型|是否支持|
|--|:-:|
|Ascend 910C|×|
|Ascend 910B|√|
|Ascend 310B|×|
|Ascend 310P|√|
|Ascend 910|×|


>![](public_sys-resources/icon-notice.gif) **须知：** 
>针对Ascend 910B，当前仅支持该系列产品中的Atlas 800I A2 推理产品。
>针对Ascend 310P，当前仅支持该系列产品中的Atlas 300I Duo 推理卡+Atlas 800 推理服务器（型号：3000）。

## 功能说明<a name="section20806203412478"></a>

通过回调函数自定义添加数组属性。

## 函数原型<a name="section1121883194711"></a>

```CPP
template <Level levelAttr = level, typename T>
Profiler &ArrayAttr(const char *attrName, const T &startIter, const T &endIter, typename ArrayCollectorHelper<Profiler<level>, T>::AttrCollectCallback callback)
```

## 参数说明<a name="section11506138144714"></a>

**表 1**  参数说明

|参数名|输入/输出|说明|
|--|--|--|
|attrName|输入|属性名。|
|startIter|输入|任意的迭代器开始。|
|endIter|输入|任意的迭代器结束。|
|callback|输入|回调函数第一个入参是当前对象，可以调用它添加属性，第二个入参是当前迭代，可以用它获取需要记录的属性内容。|


## 返回值说明<a name="section8800235121218"></a>

Profiler&返回当前对象，支持链式调用。

