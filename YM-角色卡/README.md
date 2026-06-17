# YM-角色卡

人物角色卡提示词节点。当前阶段只输出提示词，用来测试角色卡相关提示词质量。

本插件不负责生图，不调用 gpt-image2.0。gpt-image2.0 只是后续下游生图节点的目标模型。

系统提示词单独放在 `prompt_templates/` 文件夹里，全部是 `.txt` 文件，需要调整 LLM 行为时直接修改对应文件。

## 节点

### 角色卡 提示词生成器

输入：

- `prompt_type`: 提示词类型下拉菜单
  - 人物三视图
  - 人物面部三视图
  - 人物面部增强三视图
  - 人物角色卡
- `face_reference_image`: 面部参考图，可选
- `outfit_reference_image`: 服装参考图，可选
- `character_brief`: 角色简介/生成要求，写角色身份、年龄感、气质、核心外貌、服装方向、额外限制和偏好
- `rh_model`: RH LLM 模型下拉菜单
- `visual_style_preset`: 视觉风格下拉菜单
- `custom_visual_style`: 自定义视觉风格补充；当 `visual_style_preset` 选择“自定义”时，只使用这里填写的风格
- `api_config`: 可选，来自 RH OpenAPI Settings；RH 环境已配置时可以不接

输出：

- `提示词`

## 提示词模板文件

- `prompt_templates/人物三视图系统提示词.txt`: 人物三视图
- `prompt_templates/人物面部三视图系统提示词.txt`: 人物面部三视图
- `prompt_templates/人物面部增强三视图系统提示词.txt`: 人物面部增强三视图
- `prompt_templates/人物角色卡系统提示词.txt`: 人物角色卡
- `prompt_templates/服装参考图系统提示词.txt`: 服装参考图规则

## 推荐流程

1. 选择提示词类型和 RH 模型。
2. 填写角色简介/生成要求，并按需接入面部参考图、服装参考图。
3. 运行节点，输出提示词后接到 gpt-image2.0 生图节点。
