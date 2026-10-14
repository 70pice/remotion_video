# 首两镜排版问题：实际调用、代码证据与返工

用户消息 `om_x100b63cd203600a4ce35769921504c1` 的两张红框截图已实际打开，分别对应r11的shot-01、shot-02。核心问题是可见的上下/左右裁切、重复表达、素材过小和大量无效留白，不能用“初稿”掩盖。上一轮已看到问题仍呈递，监督呈递未达到应有质量。

## 是否由 Claude Code + GLM 写出

是此组合生成摄影方案。只读查询操作 `41f5616c3ea84ec1b63972b42880a02f` 的实际持久化回执：`cli_provider=claude_code_cli`、`model=glm-5.3[1m]`、`reasoning_effort=xhigh`、`context_tokens=1000000`、`mode=structured`、状态COMPLETED。

更准确的边界是：GLM输出`shots/set_design/parts`等镜头配置；已有Remotion组件和生产渲染器解释配置，并非这次自由生成React源码。`JsonModel.call`的摄影请求是无工具结构化任务，禁止读取本机文件或调用工具，模型输出之后才渲代表帧。因此不能声称它看过实际PNG后确认“都可读”。原方案的`visual_action`写了“全部在场可读”，实际图否定了这句描述。

## 为什么结构校验没拦住

- [摄影配置生成](../../../videoagents/nodes/director.py:788)调用模型后解析镜头，并展开组件套。[套解析](../../../videoagents/tools/component_sets.py:33)补齐登记部件；[套布局检查](../../../videoagents/tools/component_sets.py:119)要求全部部件，不允许直接遗漏。同一个items数组在A02/B12内绑定多个组件，容易重复。parts的时间与box可调整，不是不能改槽尺寸；也可换适合内容的套。
- [生产套渲染器](../../../src/video-production/ProductionComponentSetScene.tsx:130)使用952×1304内容区换算box。旧操作实际shot-01的步骤槽是约456×210像素；shot-02的步骤槽约476×220像素。模型沿用了默认几何尺寸。
- [ProgressSteps](../../../src/components/component-horizontal/rve/progress-steps.tsx:131)内部保留固定圆圈、连接线、标题间距、可换行的固定字号；[套渲染调用](../../../src/video-production/ProductionComponentSetScene.tsx:291)没有传槽宽高作文字高度适配。三行长文换行超过盒子，内外层`overflow:hidden`裁掉文本。
- [WordFlip生产字号](../../../src/video-production/ProductionComponentSetScene.tsx:284)只按盒宽高取34～62px，不考虑实际句子宽度。[原组件宽度测量](../../../src/components/component-horizontal/snapcn/word-flip/index.tsx:159)是词与词的几何对齐，取最长词的宽度，并未缩进父槽。[不换行文本](../../../src/components/component-horizontal/snapcn/word-flip/index.tsx:383)及max-content尺寸让长句横向溢出，被外层裁掉。
- [配置检查](../../../videoagents/tools/component_sets.py:112)检查安全区、归一化最小box、同屏几何不重叠，以及入场/阅读时长；[内容检查](../../../videoagents/tools/timeline.py:573)检查字段、条数和字数。这些不是浏览器排版边界检查。
- [代表帧生成](../../../videoagents/nodes/director_demo.py:84)每镜渲模型选定的一帧；[PNG检查](../../../videoagents/nodes/director_review.py:37)检查文件格式、画幅、产物一致性。该生产链没有文字scrollWidth/scrollHeight越界检测，也没有把PNG交给模型自动回看或逐帧视觉验收。机器通过不能代表视觉质量通过。

这些是源码和实际配置事实，不能据此断言模型内部思考过程，也不能预测具体跳出率。可见阅读障碍和首屏爆点损坏，足以要求返工。

## 本次实际动作

用户的画面意见经正常`videoagents resume --decision revise`记录为真实摄影返工，待办绑定`557958d114ed32e1117e04f7b1d06d34`；没有伪造整包通过，也没有携带reviewed_shot_ids。返工文件：[画面要求](photography-visual-reflow-feedback-20261014.txt)。要求重新编排层级、槽容量、截图主体、每处信息分工；不是全局缩字号或换颜色。其余已发现裁切、重复、单位及模板词问题同时列明。

本次保持同一个r11、同一视频分支。实际新操作 `7d4cb114779b488190906e66c605cc0f` 沿Claude Code + GLM-5.3提交；[启动复验](photography-visual-reflow-start-verification-20261014.json)证明原12件文件、32笔已有操作、16张原PNG未变，七段口播与Brief未变。原包保留为历史，尚未把它替换为合格成品。

当前只修这期实际摄影方案，没有声称共性代码已修好。后续若修系统，应在独立维护分支对真实组件渲染建立能检出这些裁切的回归检查，再修盒尺寸适配和溢出阻断；不是只添加一条“注意排版”的提示。组件套允许选删部件则属于契约变更，须同时处理Python/JS验证与组件统计。
