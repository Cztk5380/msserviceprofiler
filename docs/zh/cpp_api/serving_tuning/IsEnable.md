# IsEnable<a name="ZH-CN_TOPIC_0000002149188972"></a>

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
>针对Ascend 910B，当前仅支持该系列产品中的Atlas 800I A2 推理服务器。
>针对Ascend 310P，当前仅支持该系列产品中的Atlas 300I Duo 推理卡+Atlas 800 推理服务器（型号：3000）。

## 功能说明<a name="section20806203412478"></a>

判断是否使能采集数据，当入参级别小于配置的级别时，返回true。

## 函数原型<a name="section1121883194711"></a>

```CPP
inline bool IsEnable(Level msgLevel = level)
```

## 参数说明<a name="section11506138144714"></a>

**表 1**  参数说明

|参数名|输入/输出|说明|
|--|--|--|
|msgLevel|输入|定义的采集等级，参见创建采集配置文件中的profiler_level。|


## 返回值说明<a name="section16621124213476"></a>

true表示使能数据采集，false表示未使能。

