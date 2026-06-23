---
name: figma-analyzer
description: "解析 figma.com 设计稿:UI 结构分析、组件识别、切图与尺寸标注,必须在技术方案前完成。出现 figma.com 链接、需要把设计稿转成实现前置分析时使用。触发词:figma.com、Figma、设计稿、UI 分析、切图、组件识别"
---

# Figma UI 分析 Skill

## 触发条件

用户提供 `figma.com` 链接。**必须在技术方案之前完成，禁止跳过。**

## 依赖 Skill

本 skill 负责分析阶段。实现阶段需配合以下 skill：

| Skill | 用途 | 何时加载 |
|-------|------|---------|
| `design-system` | 颜色/间距/字体 token 速查 | 分析阶段即需 |
| `uikit-impl-patterns` | CAGradientLayer frame 时机、blur mask、designWidth、层级顺序等实现坑点 | 编码阶段 |
| `figma-to-swiftui` | SwiftUI 页面的布局还原规范 | 编码阶段（SwiftUI 页面） |

---

## 执行流程

```
用户提供 figma.com 链接
        │
        ▼
Phase 1  读取设计稿（Step 1-2）
        │
        ▼
Phase 2  结构分析（Step 3-7）
        │  每步有必填输出，缺一不可
        ▼
Phase 3  资源清单（Step 8）
        │
        ▼
Phase 4  输出文档（Step 9-10）
        │
        ▼
Gate     自检清单 ← 全部通过才能交付
        │
        ▼
等用户确认 → 才能进入技术方案
```

---

## Phase 1 — 读取设计稿

### Step 1. 提取 Figma 数据

```
mcp__figma__get_figma_data(fileKey, nodeId)
```

- 从 URL 提取 fileKey（`figma.com/(file|design)/<fileKey>/...`）
- 如有 node-id 参数，使用 nodeId 定位具体节点
- 逐一读取每个页面/组件节点

### Step 2. 确认设计基准宽度

读取 Figma 文件根节点 frame 尺寸，确认设计基准宽度（通常为 375pt 或 390pt）。

**禁止沿用旧代码里的 designWidth，每次都要从 Figma 数据确认。**

---

## Phase 2 — 结构分析

### Step 3. 布局与区域分析

**按功能职责划分区域，不以 Figma 节点层级为依据。**

#### 必须确认的维度

| 维度 | 分析内容 |
|------|---------|
| 区域划分 | 按功能划分（导航 / 内容 / 输入 / 操作 / 浮层等） |
| 摆放位置 | 每个元素在区域内的相对定位方式 |
| 层叠关系 | ZStack 层级、哪些元素浮于其他元素之上 |
| 滚动行为 | 哪个区域可滚动、Header 是否吸顶、底部是否固定 |
| 安全区 | 是否需要 ignoresSafeArea、哪个方向 |

#### 常见功能区域

- 导航区域（Navigation）— 标题、返回、操作按钮
- 内容区域（Content）— 主要信息展示
- 对话区域（Conversation）— 消息列表
- 输入区域（Input）— 文字输入、语音按钮
- 编辑区域（Editor）— 表单、选项
- 操作区域（Action）— 底部按钮、CTA
- 浮层区域（Overlay）— 弹窗、Toast、蒙层

#### 必填输出：ASCII 布局图

```
┌─────────────────────────────────────┐
│  ▍导航区域 (Navigation)  — 固定顶部  │
│  [BackButton]   TitleLabel   [More] │
├─────────────────────────────────────┤
│  ▍内容区域 (Content) — 可滚动        │
│  ┌─ CardView ────────────────────┐  │
│  │  AvatarView  ContentText      │  │
│  └───────────────────────────────┘  │
│  ~~~ BottomGradientMask (渐变蒙层) ~~│
├─────────────────────────────────────┤
│  ▍操作区域 (Action)  — 固定底部      │
│  [PrimaryButton]                    │
└─────────────────────────────────────┘
```

标注规范：
- `▍区域名 (English)` = 功能区域 + 布局行为（固定/滚动/浮层）
- `ComponentName` = 组件名称（与代码命名对应）
- `[ComponentName]` = 可交互组件
- `~~~` = 渐变/蒙层
- `*动态*` = 数据来自接口

---

### Step 4. 设计属性提取

对每个 UI 元素提取属性并对齐设计系统：

| 属性 | 对齐目标 |
|------|---------|
| 填充颜色 | `AppColors.xxx`（查 `design-system` skill） |
| 间距/边距 | `AppSpacing.xxx`（xs/sm/md/lg/xl/xxl） |
| 字号/字重 | `AppTypography.body/heading/caption(size, weight:)` |
| 圆角 | `.cornerRadius(n)` 或 `.clipShape(RoundedRectangle(...))` |
| 渐变 | `AppColors.primaryGradient` 或其他预定义渐变 |
| 描边 | borderWidth / borderColor |
| 效果 | blur / shadow / backdrop-filter |

#### Figma 属性精确解析规则（强制，禁止省略）

**规则 A：填充透明度（最高频错误来源）**

Figma API 的 fill 有两个独立透明度字段：
- `fill.color.a` — 颜色自身的 alpha 通道
- `fill.opacity` — fill 级别的 opacity（可选字段，默认 1.0）

**实际显示透明度 = `fill.color.a × fill.opacity`**

```json
// 示例：这不是纯白！是白色 26% 透明度
"fills": [{ "opacity": 0.26, "color": { "r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0 } }]
```
→ iOS: `UIColor.white.withAlphaComponent(0.26)` ✅
→ iOS: `UIColor.white` ❌（只看了 color.a=1.0，漏了 fill.opacity=0.26）

**禁止只读 `color.a` 而忽略 `fill.opacity`。必须两者相乘。文本 fill 同理。**

**规则 B：圆角换算**
- `cornerRadius >= height/2` → 全胶囊，实际值使用 `min(radius, height/2)`
- `cornerSmoothing > 0` → `layer.cornerCurve = .continuous`

**规则 C：文本属性**
- `characters` 字段是原文，**直接使用，不翻译不改写**
- text fill.opacity 同样需要乘算
- `textCase: "TITLE"` → iOS 不需要手动处理，保持原文

#### 必填输出：属性解析表（每个交互元素一张）

| 属性 | Figma 原始值 | 计算过程 | iOS 代码值 |
|------|-------------|---------|-----------|
| fill | color=#fff a=1.0, opacity=0.26 | 1.0×0.26=0.26 | `.white.withAlphaComponent(0.26)` |
| cornerRadius | 30 (height=54) | 30 > 54/2=27 → clamp | `27` |
| cornerSmoothing | 0.6 | >0 → continuous | `layer.cornerCurve = .continuous` |
| font | Montserrat Bold 16 | — | `AppTypography.heading(16, weight: .bold)` |

**禁止跳过此表。没有这张表，技术方案阶段会丢失 Figma 精确数据。**

---

### Step 5. 背景与蒙层分析（Background Spec）

> **这是项目历史上最容易失真的环节。必须产出结构化 Background Spec，禁止自由描述。**

#### 5.1 背景类型确认

| 维度 | 分析内容 |
|------|---------|
| 背景样式 | 纯色 / 渐变 / 图片 / 模糊（Material） |
| 渐变蒙层 | 是否存在、方向、透明度范围、覆盖高度 |
| 叠加层 | 半透明遮罩、毛玻璃效果、阴影 |
| 背景层级 | 每一层的 addSubview 顺序 |

#### 5.2 分层职责识别

每个页面的背景可能由多层组成，必须先区分职责再输出参数：

| 层类型 | 职责 | 特征 |
|--------|------|------|
| 背景底图 | 页面底色 | 全屏 fixed，alpha=1 |
| 底色渐变 | 页面底部或顶部的色调过渡 | alpha=1，通常从某 y 值延伸到屏幕边缘 |
| 遮挡渐变 | 遮住列表/内容末尾，制造淡出效果 | alpha 从 0 渐变到不透明，覆盖在内容之上 |
| blur 容器 | 毛玻璃材质 | `UIVisualEffectView` |
| blur mask | 让 blur 边缘柔和淡出 | CAGradientLayer 作为 blur.layer.mask |

**两种渐变层的高度、起始位置、stop 颜色可能完全不同，必须分别输出，不允许合并描述。**

#### 5.3 必填输出：Background Spec 表

对每个页面/弹窗，输出以下结构化表格：

```markdown
### Background Spec: {页面名}

| 字段 | 值 |
|------|-----|
| 设计宽度 | 390 |
| 背景类型 | image + overlay gradient + blur mask |
| safe area | top: true, bottom: true |
| 滚动行为 | 背景固定，内容滚动 |

#### 图层清单

| Layer | 类型 | 描述 |
|-------|------|------|
| 0 | 背景图 | `bg_home_main`, 全屏 fixed |
| 1 | 底色渐变 | 紫→深紫, 从 y=400 到底部 |
| 2 | 内容 ScrollView | 可滚动区域 |
| 3 | 遮挡渐变 | 透明→不透明, 底部 96pt |
| 4 | blur 容器 | systemUltraThinMaterialLight |

#### 渐变参数（每层独立）

**Layer 1 — 底色渐变：**

| 参数 | 值 |
|------|-----|
| startPoint | CGPoint(x: 0.5, y: 0) |
| endPoint | CGPoint(x: 0.5, y: 1) |
| colors | [UIColor(...).cgColor, UIColor(...).cgColor] |
| locations | [0.0, 0.8] |
| 高度 | 全屏 |

**Layer 3 — 遮挡渐变：**

| 参数 | 值 |
|------|-----|
| startPoint | CGPoint(x: 0.5, y: 0) |
| endPoint | CGPoint(x: 0.5, y: 1) |
| colors | [UIColor(r, g, b, alpha: 0).cgColor, UIColor(r, g, b, alpha: 0.9).cgColor] |
| locations | [0.0, 0.7435] |
| 高度 | 96pt（局部） |

#### blur 参数（如有）

| 参数 | 值 |
|------|-----|
| style | systemUltraThinMaterialLight |
| 实现方式 | makeAdaptiveGlassChrome |
| 需要 mask | 是，与 Layer 3 相同 locations |
| mask colors | [UIColor.white.cgColor, UIColor.white.cgColor, UIColor.clear.cgColor] |
| mask locations | [0.0, 0.5097, 1.0] |
```

#### 5.4 渐变数据提取规则

**禁止凭视觉推断。必须逐一读取 Figma 节点数据：**

1. 对每一个渐变/蒙层视图，必须：
   - 用 `mcp__figma__get_figma_data(nodeId)` 读取对应节点
   - 提取 `fills[].gradientStops` 的精确 rgba + position
   - 确认节点的绝对 y、高度、是否覆盖全屏或局部

2. **locations 字段必须显式填写，禁止留空或写 nil。** 如果 Figma 只有两个等距 stop，locations 也要写 `[0.0, 1.0]`。

3. 每个渐变层输出可直接粘贴的代码片段：

```swift
// 示例：列表底部遮挡渐变
grad.colors    = [UIColor(red: 246/255, green: 240/255, blue: 255/255, alpha: 0).cgColor,
                  UIColor(red: 246/255, green: 240/255, blue: 255/255, alpha: 0.9).cgColor]
grad.locations = [0.0, 0.7435]
grad.startPoint = CGPoint(x: 0.5, y: 0)
grad.endPoint   = CGPoint(x: 0.5, y: 1)
```

#### 5.5 blur + mask 联动规则

| 场景 | 必须做什么 |
|------|-----------|
| 设计稿底部有 blur + 渐变透明 | blur 必须加 gradient mask，locations 与遮挡渐变一致 |
| blur 在浅色背景上 | blurStyle 必须选 Light 后缀（如 `.systemUltraThinMaterialLight`） |
| blur 在深色背景上 | 注意采样后会呈深灰，可能需要 tintColor 调整 |
| 需要边缘柔和 | mask 的 white→clear 方向与淡出方向一致 |

**毛玻璃实现统一使用 `makeAdaptiveGlassChrome`（`UIView+GlassEffect.swift`），禁止业务内散装 UIBlurEffect。**

---

### Step 6. 动态元素与动效识别

#### 必须确认的维度

| 维度 | 分析内容 |
|------|---------|
| 动态数据 | 哪些文字/图片/状态来自接口（需绑定 ViewModel 属性） |
| 条件显隐 | 哪些元素根据状态动态显示/隐藏 |
| 列表/循环 | 哪些区域是动态列表（ForEach / UITableView / UICollectionView） |
| 可能的动效 | 进场动画、状态切换过渡、按钮反馈、加载骨架屏 |
| 交互手势 | 点击 / 长按 / 滑动 / 拖拽 |
| 动态尺寸 | 列表区域高度是固定值还是需要自适应屏幕剩余空间 |

#### Figma 绝对坐标 → 约束转换规则

| Figma 数据 | 错误做法 | 正确做法 |
|-----------|---------|---------|
| 元素绝对 x/y | 直接用 `offset(x)` / `offset(y)` | 转换为相对约束（relative to parent / sibling） |
| 兄弟元素之间的间距 | 用各自的绝对 y 定位 | `elementB.top = elementA.bottom + gap` |
| 同行元素的水平位置 | 固定 x offset | `centerX.equalToSuperview()` 或相对兄弟定位 |

#### 固定高度 vs 动态高度决策

- 设计稿只展示了一种行数 → 不代表高度固定，需确认内容是否会变化
- 有月份切换 / 文字长度不定 / 列表内容不定 → 动态高度
- 动态高度组件必须写明回调方式和外部响应机制

#### 外观相似节点的歧义处理

当 Figma 中存在外观相同或相似的多个图标/按钮节点时，必须：
1. 逐一读取每个节点的 Figma 注释 / 名称 / 父节点名称
2. 结合绝对坐标（y 值从小到大）确认视觉顺序
3. 明确写出："节点 A（y=xx）= 功能甲；节点 B（y=xx）= 功能乙"
4. 如无法确认，提出具体问题，等用户回答后再继续。**不允许写"功能待确认"后继续。**

---

### Step 7. 组件识别

#### 7.1 iOS 系统原生组件识别

判断设计图中哪些 UI 效果是 iOS 系统自带能力：

| 系统组件/效果 | 识别特征 | 实现方式 |
|--------------|---------|---------|
| NavigationBar | 顶部标题 + 左返回右操作按钮 | `UINavigationController` 自带 |
| TabBar | 底部图标 + 文字 Tab 切换 | `UITabBarController` 自带 |
| Sheet / 半屏弹窗 | 底部弹出、可下拉关闭、有圆角 | `UISheetPresentationController` |
| Alert / ActionSheet | 系统风格弹窗/底部操作列表 | `UIAlertController` |
| 系统模糊背景 | 毛玻璃半透明效果 | `makeAdaptiveGlassChrome` |
| 下拉刷新 | 列表顶部下拉出现 spinner | `UIRefreshControl` / `.refreshable {}` |
| 滑动删除 | 列表项左滑出现操作按钮 | `.swipeActions {}` |
| SF Symbols 图标 | 系统内置矢量图标 | `UIImage(systemName:)` 无需下载 |
| Toggle / Slider | 系统风格开关和滑块 | SwiftUI `Toggle` / `Slider` |
| DatePicker | 日期/时间选择器 | SwiftUI `DatePicker` |
| ProgressView | 加载 spinner / 进度条 | SwiftUI `ProgressView` |

**必填输出：每个元素标注三类之一**
- ✅ **系统原生** — 直接用系统 API
- ⚠️ **系统原生 + 定制** — 基于系统组件但需调整样式
- ❌ **完全自定义** — 需手动实现

#### 7.2 项目内组件与扩展识别

**先查已有，再决定新建：**

| 查找位置 | 内容 |
|---------|------|
| `Common/Components/` | RemoteImage / AppAlert / CheckInSheetContainer / LoadingOverlayView 等 |
| 各模块 `Components/` | 模块内组件 |
| `Common/Extensions/` | 通用 UI / 工具扩展 |

**扩展优先映射表：**

| 设计现象 | 优先使用 | 文件 |
|----------|---------|------|
| 毛玻璃 / 材质 / 玻璃描边 | `UIVisualEffectView.makeAdaptiveGlassChrome(...)` | `UIView+GlassEffect.swift` |
| 全角圆角 | `UIView.roundAllCorners(_:)` | `UIView+Extensions.swift` |
| 指定角圆角 | `UIView.cornerRadius(_:corners:)` | `UIView+Extensions.swift` |
| 日期/打卡日/格式化 | `Date+Extensions.swift` | 同目录 |
| 字符串处理 | `String+Extensions.swift` | 同目录 |
| loading / 加载遮罩 | `view.showLoading()` / `view.hideLoading()` | `LoadingOverlayView.swift` |

**必填输出：在「复用组件」中写明将使用的扩展入口。**

---

## Phase 3 — 资源清单

### Step 8. 资源下载

**原则：能从 Figma 切图的直接下载使用，不手动代码绘制。**

#### 切图 vs 代码实现决策表

| 情况 | 结论 |
|------|------|
| 非 SF Symbols 图标 | ✅ 下载切图 |
| 复杂渐变背景 / 纹理背景 | ✅ 下载切图 |
| 插图 / 装饰性图片 | ✅ 下载切图 |
| 卡片纹理底 / 特殊容器背景 | ✅ 下载切图 |
| 操作按钮图标（含圆底 + 图形组合） | ✅ 下载切图 |
| 纯色背景 | ❌ 代码实现 |
| 简单线性渐变（2 色，方向单一） | ❌ 代码实现 |
| 圆角矩形 / 圆形 | ❌ 代码实现 |
| SF Symbols 已有的图标 | ❌ 系统图标 |

#### 资源格式规则

| 类型 | 格式 | 说明 |
|------|------|------|
| 图标 | SVG（优先）/ PNG @2x | 复杂渐变图标用 PNG |
| 背景图 | PNG @2x 或 JPEG | 有透明用 PNG，实底用 JPEG |
| 插图 | PNG @2x / SVG | 空状态、引导页 |
| 头像框/装饰 | PNG @2x | 边框、角标、徽章 |

#### Scale 规则

- `@2x` imageset slot → Figma API `scale=2`
- `@3x` imageset slot → Figma API `scale=3`
- 验证：`sips -g pixelWidth` 结果应 = `设计pt × scale`

#### 背景图导出排除规则

全帧导出时，Figma 中的 Status Bar / Home Indicator 会渲染进图片，与真机系统 UI 重叠。

**必须排除的节点：**
- name 含 `nav` / `Status Bar` / `Home Indicator` → 系统占位层
- 按钮 / 输入框 / 可点击组件 → 交互元素
- **保留**：logo、插图、分割线、渐变光斑 → 装饰层

**导出后自查：**
- [ ] 顶部无 9:41 时间 / 信号图标
- [ ] 底部无 Home Indicator 横条
- [ ] 无按钮/输入框图形残留
- [ ] 装饰元素完整保留
- [ ] JPEG 无黑底 / PNG 透明区域正确

#### 必填输出：资源清单表

| 资源名 | nodeId | 格式 | 保存路径 | 说明 |
|--------|--------|------|---------|------|
| icon_back | 1234:5678 | SVG | Assets/Icons/ | 返回按钮 |
| bg_home_main | 1234:9012 | PNG @2x | Assets/Backgrounds/ | 首页背景 |

**每个用 UIImageView / UIButton 展示的视觉区域，必须在此表中有对应条目。不允许"待确认"空项。**

---

## Phase 4 — 输出文档

### Step 9. 设计系统对齐检查

| 检查项 | 结论 |
|--------|------|
| 所有颜色均可用 AppColors 覆盖 | ✅ / ❌（需新增 xxx） |
| 所有间距均可用 AppSpacing 覆盖 | ✅ / ❌ |
| 所有字体均可用 AppTypography 覆盖 | ✅ / ❌ |

### Step 10. 输出 UI 分析文档

保存到 `Docs/features/{feature}/UI分析.md`。

---

## UI分析.md 输出模板

```markdown
# {功能名称} UI 分析

## 设计基准

| 字段 | 值 |
|------|-----|
| Figma 链接 | {url} |
| 设计宽度 | {designWidth}pt |
| 目标框架 | UIKit / SwiftUI |

---

## ASCII 布局图

（Phase 2 Step 3 的输出）

---

## 页面结构

### 区域 1: {名称}（如 Navigation）
- 定位方式：固定顶部 / 吸顶 / 随滚动
- 布局：UIStackView(.horizontal) / SnapKit 约束
- 背景：UIColor(AppColors.xxx) / CAGradientLayer / 透明

#### 组件清单

| 序号 | 组件 | UIKit 类型 | 属性 | 动态/静态 |
|------|------|-----------|------|----------|
| 1 | titleLabel | UILabel | font: AppTypography.heading(20), textColor: AppColors.white | 动态 |

#### 属性解析表

（Phase 2 Step 4 的输出，每个交互元素一张）

### 区域 2: {名称}
...

---

## Background Spec

（Phase 2 Step 5 的完整输出，包含图层清单、渐变参数、blur 参数）

---

## 动效与交互

| 元素 | 动效类型 | iOS 实现 |
|------|---------|---------|
| Card | 进场 | UIView.animate(duration: 0.3) |
| 按钮 | 点击反馈 | Haptics.impact() |

---

## 动态元素映射

| UI 组件 | 数据来源 | 绑定方式 | 空态处理 |
|--------|---------|---------|---------|
| titleLabel | ViewModel.userName | withObservationTracking | 默认文案 |
| avatarView | ViewModel.avatarURL | RemoteImage | placeholder |

---

## iOS 系统原生组件

| UI 元素 | 判定 | 实现方式 | 定制项 |
|--------|------|---------|--------|
| 顶部导航栏 | ✅ 系统原生 | UINavigationController | 透明背景 |
| 卡片组件 | ❌ 完全自定义 | 手动实现 | — |

---

## 复用组件

| 组件/扩展 | 来源 | 用途 |
|----------|------|------|
| RemoteImage | Common/Components | 头像加载 |
| makeAdaptiveGlassChrome | UIView+GlassEffect.swift | 卡片毛玻璃 |
| roundAllCorners | UIView+Extensions.swift | 卡片圆角 |

---

## 需新建组件

| 组件名 | 放置路径 | 说明 |
|--------|---------|------|

---

## 资源清单

（Phase 3 Step 8 的输出，含 nodeId）

---

## 设计系统对齐

（Phase 4 Step 9 的输出）

---

## UI 设计方案

### 区域架构

| 区域 | 定位方式 | 相对位置 | UIKit 布局 |
|------|---------|---------|-----------|
| 导航区域 | 固定顶部 | 顶部，安全区内 | 自定义 UIView + SnapKit |
| 内容区域 | 可滚动 | 导航下方，操作上方 | UIScrollView |
| 操作区域 | 固定底部 | 底部，安全区外 | UIView + SnapKit |

### 自定义组件设计

#### {ComponentName}: UIView

- **职责**：一句话说明
- **位置**：所在区域 + 相对位置
- **内部布局**：UIStackView / SnapKit 约束描述
- **输入**：`func configure(with model: Xxx)`
- **交互**：UIButton target-action / 闭包回调
- **样式**：backgroundColor / cornerRadius / 间距
- **状态变化**：不同状态下的 UI 差异
```

**输出后停止，等用户确认 ASCII 布局图、Background Spec 和 UI 设计方案正确后，再进入技术方案。**

---

## 自检清单

**文档交付前，逐项自检。全部通过才能提交给用户：**

### 结构完整性

- [ ] 有 ASCII 布局图，按功能区域划分
- [ ] 每个区域有组件清单表
- [ ] 每个交互元素有属性解析表（含 Figma 原始值 → 计算过程 → iOS 代码值）
- [ ] 属性解析表中，所有 fill 都做了 `color.a × fill.opacity` 乘算
- [ ] 有完整的 Background Spec（图层清单 + 渐变参数 + blur 参数）
- [ ] Background Spec 中每个渐变层都有 startPoint / endPoint / colors / locations / 高度
- [ ] **所有渐变 locations 字段已显式填写，无 nil / 无缺省**
- [ ] 有 blur + mask 联动说明（如页面有 blur）
- [ ] 有系统组件分类表（✅/⚠️/❌ 标注）
- [ ] 有复用组件清单（含扩展入口名称）
- [ ] 有资源清单表（含 nodeId）
- [ ] 有设计系统对齐检查
- [ ] 有 UI 设计方案

### 数据精确性

- [ ] 设计基准宽度从 Figma 根节点确认，未沿用旧值
- [ ] 渐变 stop 从 Figma API gradientStops 精确提取，未目测估算
- [ ] 圆角做了 `min(radius, height/2)` 钳制检查
- [ ] 外观相似节点已通过坐标 + 名称消歧
- [ ] 资源清单无"待确认"空项

### 一致性

- [ ] 颜色引用 AppColors，无裸 hex / UIColor(red:)
- [ ] 间距引用 AppSpacing，无裸数字
- [ ] 字体引用 AppTypography，无裸 .system(size:)
- [ ] 毛玻璃引用 makeAdaptiveGlassChrome，无散装 UIBlurEffect
- [ ] 圆角引用 roundAllCorners / cornerRadius(_:corners:)，无散装 layer 操作
