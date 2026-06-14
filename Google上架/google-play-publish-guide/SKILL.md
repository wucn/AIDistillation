---
name: google-play-publish-guide
description: 扫描当前 Android 项目，生成一份针对「本应用」的 Google Play 上架操作步骤指南。每一步都说明该选项在 Play Console 的含义、有哪些选择，再根据扫描到的项目实情（有没有广告 SDK、有没有 .so 库、targetSdk 多少、AGP 版本、声明了哪些权限等）给出本应用该怎么选、为什么这么选。当用户要把一个 Android 应用上架到 Google Play、需要上架步骤清单、需要填 Play Console 的 App content 声明（Ads / Advertising ID / Data safety / Content rating / Target audience / Photo permissions）、需要判断是否要做 16KB 页面对齐、需要配签名或生成 AAB 时，务必使用本 skill。即使用户只是说「这个项目怎么上架」「帮我过 Google 审核」「Data safety 怎么填」也要触发。
---

# Google Play 上架指南生成器

本 skill 把一份通用上架文档变成**针对当前项目**的定制步骤。核心思路：

1. **先用脚本扫项目** → 得到一份客观事实清单（JSON）
2. **按事实查参考** → 把每个 Play Console 声明项映射到「本项目选什么、为什么」
3. **输出定制指南** → 每步含选项含义 + 本项目取舍依据

事实采集交给脚本（确定性、可复现）；判断和讲解交给模型（结合 references/）。这样既不漏 SDK，又能讲清「为什么」。

---

## 第一步：扫描项目

运行扫描脚本（项目路径通常是当前工作目录或用户指定的路径）：

```bash
python3 <本skill目录>/scripts/scan_project.py <项目根目录>
```

脚本输出一份 JSON，关键字段含义：

| 字段 | 说明 |
|------|------|
| `version_catalog` | `gradle/libs.versions.toml` 路径（null 表示项目没用版本目录）。sdk/AGP 版本优先从这里取，最可靠 |
| `gradle.applicationId / versionName` | 包标识与版本 |
| `gradle.versionCode` | 对象 `{value, computed}`。`computed=true` 表示是函数/表达式（如 `calculateVersionCode()`），**上传前必须确认实际数值递增**，脚本拿不到真值 |
| `gradle.minSdk / targetSdk / compileSdk` | SDK 版本（targetSdk≥33 → 必须声明广告 ID） |
| `agp_version` | AGP 版本（≥8.5.1 默认支持 16KB 对齐）；优先取版本目录的 `agp` key，避免被子模块的旧版 `compileOnly com.android.tools.build:gradle` 污染 |
| `native_libs.has_native_libs` | 有无 .so（决定是否需要 16KB 适配） |
| `packaging.value` | 是否已设 useLegacyPackaging |
| `permissions.photo_video_related` | 照片/媒体权限（决定是否填 5.8 声明） |
| `permissions.has_internet` | 有无联网 |
| `sdks.has_ad_sdk` | **直接决定 Ads / Advertising ID / Data safety 的广告相关勾选** |
| `sdks.has_analytics_sdk / has_crash_sdk / has_attribution_sdk / has_firebase / has_facebook_sdk` | 决定 Data safety 的 Device IDs / App activity / App info 勾选 |
| `sdks.detected_sdks` | 具体识别到的 SDK 及其标签 |
| `derived.*` | 脚本算好的派生结论（needs_16kb_check、must_declare_advertising_id 等） |
| `login_signals` | 登录功能线索（**机器判断不可靠，需人工确认**） |
| `store_assets` | 现有图标/截图 |
| `strings.has_multiple_locales` | 是否有多语言（改应用名要全语言同步） |
| `signing.release_signed` | release 是否已配签名 |

> 如果 `agp_version` 为 null，提示用户人工确认 AGP 版本（看根 `build.gradle.kts` 的 plugins 块或 `libs.versions.toml`）。
> 如果 `login_signals` 暧昧，直接问用户「应用有没有登录功能」。

---

## 第二步：查参考，做映射

扫描结果出来后，**按声明项逐个查对应参考文件**，把「选项含义」和「本项目依据」拼起来：

- **App content 声明项**（Ads / Advertising ID / Data safety / Content rating / Target audience / Photo permissions / Government / Financial / Health / Category / Store listing）→ 读 `references/console-declarations.md`，里面有每项的「这是什么 / 有哪些选择 / 依据（引用扫描字段名）/ 坑」。
- **发布轨道 / 签名 / 构建 / 包名应用名修改 / 必做·可跳过·可后补分类** → 读 `references/release-and-signing.md`。里面有「必做 / 条件必须 / 可跳过 / 可后补」四类清单，生成指南时要把每个步骤归到对应类别，让用户知道哪些是硬门槛、哪些可以先过审再补。
- **16KB 对齐** → 读 `references/16kb-alignment.md`（按 `native_libs.has_native_libs` 和 `agp_supports_16kb_default` 决定走哪个方案）。
- **常见报错 / 英文提示** → 读 `references/troubleshooting.md`。

关键映射速查（扫描字段 → 结论）：

| 扫描事实 | → 影响的声明项 | → 取值 |
|----------|----------------|--------|
| `sdks.has_ad_sdk` = true | Ads / Advertising ID / Data safety | Ads=Yes；Advertising ID=Yes；Device IDs 勾 + Advertising |
| `sdks.has_ad_sdk` = false | Ads / Advertising ID | Ads=No；Advertising ID=No |
| `derived.must_declare_advertising_id` = true (targetSdk≥33) | Advertising ID | **未声明无法发版**，必须填 |
| `likely_collects_device_ids` = true | Data safety → Device or other IDs | 勾 |
| `has_crash_sdk` / `has_analytics_sdk` | Data safety → App info and performance / App activity | 勾 |
| `has_photo_video_perms` = true | Photo and video permissions | 必填 ≤250 字符说明 |
| `login_signals` = 无登录线索 | App access | 选 `available without special access` |
| `native_libs.has_native_libs` = false | 16KB 对齐 | 无须处理 |
| `native_libs.has_native_libs` = true + `agp_supports_16kb_default` = true | 16KB 对齐 | AGP 已默认对齐，验证即可 |
| `native_libs.has_native_libs` = true + AGP<8.5.1 | 16KB 对齐 | 升级 AGP 或 useLegacyPackaging 或重编 .so |

---

## 第三步：输出定制指南

输出一份结构化的中文指南，**每个声明项都遵循下面的写法**——选项含义和本项目依据必须都写到：

```
### <声明项名> — 必填/选填 / 是否影响审核

**这是什么**：<该选项在 Play Console 的含义，1–2 句>
**有哪些选择**：<列出可选项>
**本项目怎么选**：<具体值>
**为什么这么选**：<引用扫描结果，例如「扫描到依赖了 Pangle（穿山甲）和 Adjust，属于广告+归因 SDK，因此……」>
**坑 / 注意**：<选错后果或前置条件，没有则省略>
```

指南完整结构按这个顺序：

1. **项目扫描摘要** — 一张表，列出 applicationId / versionCode / minSdk·targetSdk / 识别到的 SDK / 有无 .so / AGP / 签名就绪情况。让用户一眼看清本项目现状。
2. **上架前必做（按风险排序）** — 把扫描发现的「必须先处理」的事项前置，例如：
   - 若 `needs_16kb_check` 且 AGP 不够 → 升级 AGP
   - 若 release 未签名 → 配签名（给 local.properties + build.gradle.kts 片段）
   - 若有广告 SDK 但没有隐私政策页 → 先建隐私政策页

   每个事项旁标注它属于哪一类（🔴 必做 / 🟡 条件必须 / ⬜ 可跳过 / 🟢 可后补），分类依据见 `references/release-and-signing.md`。这样用户能分清硬门槛和可以先过审再补的东西——尤其要讲明：13 项声明提交时**必须有值**，但内容**可以上线后在 App content 页随时改、无需重新打包**。
3. **Create app** — 应用名/默认语言/App·Game/Free·Paid 的本项目取值
4. **Set up your app（全部声明项）** — 按上面四段式逐项写。这是指南主体。
   - 其中 **Data safety** 要给到 Step 级别的具体勾选清单（因为最复杂、最易错）。
5. **Release your app** — 新账号还是老账号（问用户）→ 决定要不要走 Closed testing 的 20 人 ×14 天。给 Production 发布步骤 + Release notes 模板。
6. **签名与构建** — 给出针对本项目的 `bundleRelease` 命令和输出路径；若已配 Google Play App Signing 则说明。
7. **16KB 对齐结论** — 一句话结论 + 是否需要动作。
8. **提交审核** — Publishing overview → Send for review，Managed publishing 取舍。

> 风格：写给一个能看懂 Android 项目的开发者（用户是 Android 开发者）。解释「为什么」比堆步骤更重要。Data safety、Advertising ID、照片权限声明这几个高频拒审点要讲透。

---

## 注意

- 扫描脚本是辅助，**不是权威**。依赖字符串匹配可能漏识别冷门 SDK 或被混淆名绕过；登录功能机器判断不可靠。遇到关键声明（尤其 Ads、App access），把扫描结论作为「建议」，并提示用户最终以代码实际行为为准——**Google 看实际行为，不看声明意图**。
- 隐私政策内容必须和 Data safety 声明逐项一致，这是最常见的拒审原因，指南里要反复强调。
- `applicationId`、签名、versionCode 这些一旦上线就难改，指南里要单列「不可逆决策」提醒。
