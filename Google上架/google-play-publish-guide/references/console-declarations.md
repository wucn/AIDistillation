# Play Console 声明项参考（App content / Store listing）

本文件是扫描结果 → Play Console 取值的「映射字典」。每项给出：
- **这是什么**：选项在 Play Console 的含义
- **有哪些选择**：可选值
- **依据**：当扫描结果出现某项事实时，应怎么选、为什么
- **坑**：选错的后果

路径提示：左侧菜单 **Monitor and improve → Policy and programs → App content** 可重新编辑所有声明项。

---

## 1. Privacy policy（隐私政策）— 必填，影响审核

- **这是什么**：填一个可公开访问（无需登录）的隐私政策网页链接，如 `https://example.com/privacy`。
- **内容必须包含**：收集哪些数据 / 数据用途 / 是否分享第三方 / 用户如何删除数据 / 联系方式。
- **依据**：
  - 只要扫描到 `has_ad_sdk / has_analytics_sdk / has_attribution_sdk` 任一为真 → 隐私政策里**必须**写明「收集设备标识符 / 广告 ID，用于广告与分析」，且要和 Data safety 声明逐项对得上。
  - 扫描到 `has_photo_video_perms` 为真 → 写明照片访问用途（如「仅在本地处理，不上传」或「上传到服务器处理」要和 Data safety Step 4 的 ephemeral 选择一致）。
- **坑**：隐私政策内容和 Data safety 不一致是最常见拒审原因。两者必须互相印证。
- **快速建页**：用 Google Sites（sites.google.com）新建页面，粘贴文字后 Publish，得到 `https://sites.google.com/view/xxx-privacy/home` 链接。

## 2. App access（应用访问）— 必填，影响审核

- **这是什么**：审核员是否需要登录才能用你的应用。
- **选择**：
  - `All functionality is available without special access` — 无需登录
  - `All or some functionality is restricted` — 需要登录（必须提供测试账号密码）
- **依据**：以 `login_signals` 为参考，**但机器判断不可靠，务必人工确认**。无登录功能就选第一个；有登录就选 restricted 并附上**不会过期的测试账号**。
- **坑**：选了 restricted 却没给有效测试账号 → 审核员进不去 → 直接拒。

## 3. Ads（广告）— 必填，影响审核

- **这是什么**：你的应用有没有广告。
- **选择**：`Yes, my app contains ads` / `No, my app does not contain ads`
- **依据**：直接看 `sdks.has_ad_sdk`。
  - 真 → Yes
  - 假 → No
- **坑**：选 No 但实际有广告 SDK（含第三方）→ 判 **Deceptive behavior（欺骗行为）**拒审或下架。暂时关闭了广告 SDK 才能选 No。

## 4. Content rating（内容分级）— 必填，影响审核

- **这是什么**：填问卷（IARC）得到内容分级，显示在商店页。
- **工具类（Utility）应用标准答案**：Category=`Utility`，其余所有问题（Downloaded App / User Content Sharing / Online Content / Age-Restricted Products / Miscellaneous）全部选 **No** → 最终 `Everyone / PEGI 3`，最宽松。
- **依据**：本项目若为纯工具类，照填 Utility + 全 No。
- **坑**：每个 section 默认折叠，要逐一点开选，全部 Completed 后 Next 才亮。虚报会被下架。

## 5. Target audience（目标受众）— 必填，影响审核

- **这是什么**：应用面向哪个年龄段。
- **依据**：工具类含广告应用 → 选 **18 and over**（最安全、审核最宽松）。
- **坑**：**不是儿童应用绝对不要勾 13 岁以下**，否则触发 COPPA + Families Policy，审核极严。

## 6. Data safety（数据安全）— 必填，**最容易出问题**

Google 看的是「是否收集/共享数据传出设备」，**不是**「代码里声明了什么权限」。第三方 SDK 自动上传的数据也算你的。

### Step 2 — 数据收集和安全

| 问题 | 依据 |
|------|------|
| 是否收集/共享用户数据？ | `sdks.has_*` 任一真、或 `permissions.has_internet` + 上传逻辑 → **Yes**；纯离线无任何 SDK → No |
| 传输是否加密？ | 走 HTTPS/TLS → Yes |
| 账号创建方式 | 无注册登录 → `My app does not allow users to create an account` |
| 能否用外部账号登录？ | 无 → No |
| 是否提供删除数据途径？ | 只有不保存服务器端个人数据时才可选 No；否则必须提供 |

### Step 3 — 数据类型（依据扫描结果勾选）

| 数据类型 | 勾选依据 |
|----------|----------|
| **Photos and videos → Photos** | `has_photo_video_perms` 真且处理图片 → 勾 Photos；含视频再加 Videos |
| **Device or other IDs** | `likely_collects_device_ids` 真（ad/analytics/attribution/facebook SDK 任一）→ 勾 |
| **App info and performance** | `has_crash_sdk` 或 `has_analytics_sdk` 真 → 勾 |
| **App activity** | `has_analytics_sdk` 或 `has_attribution_sdk` 真 → 勾 |
| **Location（Precise/Approximate）** | 一般纯工具两个都不勾，除非真有定位上传 |

### Step 4 — 数据使用说明（每个勾选类型分别填 Start）

**A. Photos（若图片只在本地处理）**：Collected / 临时处理视情况 / Data collection is required / 只勾 App functionality。
> 若照片**只在本地、不传出设备**，仍可能因图片访问行为需在 Step 3 勾 Photos，但隐私政策要写明 "All photo processing is local. No photos are uploaded or shared."

**B. Device or other IDs**（按扫描到的 SDK 类型）：
- 只有统计/崩溃 SDK（analytics/crash/firebase）→ Collected / No / required / 勾 Analytics
- 有广告 SDK（ad）→ Collected + 通常加 Shared / No（ephemeral）/ required / 勾 Advertising or marketing（兼统计再加 Analytics）
- 有归因 SDK（attribution）→ Collected / 可能 Shared / No / required / Analytics + Advertising or marketing

## 7. Advertising ID（广告标识符）— 必填

- **这是什么**：是否使用 Android 广告 ID。
- **依据**：
  - `derived.must_declare_advertising_id`（targetSdk ≥ 33）为真时，**未完成此声明无法提交**。
  - `sdks.has_ad_sdk` 真 → Yes；纯离线无 SDK → No。
- **坑**：targetSdk ≥ 33（Android 13+）必须声明，否则发版报 `Incomplete advertising ID declaration`。

## 8. Photo and video permissions（照片权限声明）— 必填

- **这是什么**：用了 `READ_MEDIA_IMAGES`/`READ_EXTERNAL_STORAGE`/`MANAGE_MEDIA` 等照片权限时，必须用 ≤250 字符说明核心功能。
- **依据**：`derived.has_photo_video_perms` 真时必填。
- **模板**：
  ```
  Photo recovery app. Requires photo access to browse and restore deleted images on device. All processing is local. No photos are uploaded or shared.
  ```
- **坑**：不填 → 提交报 `All developers requesting access to the photo and video permissions are required to tell Google Play about the core functionality of their app`。

## 9. Government apps / 10. Financial features / 11. Health

- Government → 一般 No（除非真是政府应用）
- Financial → `My app doesn't provide any financial features`（除非有支付/借贷/投资）
- Health → No（除非涉及健康医疗数据）
- **坑**：有相关功能却选 No → 拒审。

## 12. Select app category and contact details — 必填

- **App category**：图片/照片工具类选 `Tools`。
- **Tags**（最多 5）：`Photography`、`Photo editor` 等。其他类型按实际选。
- **Contact details**：Email 必填（显示在商店）；Phone 可选；Website 可填隐私政策链接。

## 13. Set up your store listing（商店详情页）— 必填

| 字段 | 要求 |
|------|------|
| App name | ≤30 字符 |
| Short description | ≤**80 字符（含空格标点，精确计数）** |
| Full description | ≤4000 字符，勿堆关键词（spam 会拒） |
| App icon | 512×512 PNG，32 位，**无透明** |
| Feature graphic | 1024×500 PNG/JPG |
| Phone screenshots | 2–8 张，16:9 或 9:16，**必须反映真实界面** |

- **依据**：用 `store_assets` 结果提示用户哪些素材已存在 / 还缺。
- **坑**：截图虚假、暗示与 Google/其他品牌关联、描述堆关键词都会拒。
