# event<a name="ZH-CN_TOPIC_0000002184847757"></a>

## AI处理器支持情况<a name="section8178181118225"></a>

>![](public_sys-resources/icon-note.gif) **说明：** 
>AI处理器与昇腾产品的对应关系，请参见《[昇腾产品形态说明](https://www.hiascend.com/document/detail/zh/AscendFAQ/ProduTech/productform/hardwaredesc_0001.html)》

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

## 函数功能<a name="section463019538153"></a>

记录一个事件。

## 函数原型<a name="section759854510169"></a>

```python
def event(self, event_name)
```

## 参数说明<a name="section354791521716"></a>

|参数名|输入/输出|说明|
|--|--|--|
|event_name|输入|事件名。|


## 返回值说明<a name="section776014535188"></a>

无

