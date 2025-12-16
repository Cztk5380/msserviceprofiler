# attr<a name="ZH-CN_TOPIC_0000002149370548"></a>

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

## 函数功能<a name="section463019538153"></a>

添加属性，返回当前对象，支持链式调用。在解析为trace数据之后，会显示在args中。

## 函数原型<a name="section759854510169"></a>

```python
def attr(self, key, value)
```

## 参数说明<a name="section354791521716"></a>

|参数名|输入/输出|说明|
|--|--|--|
|key|输入|属性名。|
|value|输入|属性值。|


## 返回值说明<a name="section776014535188"></a>

Profiler返回当前对象，支持链式调用。

