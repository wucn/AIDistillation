# 发布轨道、签名、构建

## 创建应用（Create app）

| 字段 | 说明 |
|------|------|
| App name | ≤30 字符 |
| Default language | `zh-CN` 或 `en-US` |
| App or Game | 一般 App |
| Free or Paid | **发布后不能从免费改付费** |

## Dashboard 三大区块

1. **Start testing now**（内部测试）— 选填，可跳过
2. **Set up your app**（应用信息）— 全部必填（见 console-declarations.md）
3. **Release your app**（发布）

完成 Set up your app 后，该区块会消失。

## 必做 / 可跳过 / 可后补 分类

生成指南时，要向用户讲清每一步属于哪一类，避免在不必要的地方卡住。

### 🔴 必须（不做无法提交/上架）
- 注册账号、创建应用（Free/Paid 一旦定不能从免费改付费）
- **13 项声明全部有值**（提交门槛）
- 构建签名 AAB（未签名直接报错）
- Production 发布 + Publishing overview → Send for review

### 🟡 条件必须（满足条件才必须）
| 项 | 触发条件 |
|----|----------|
| 16KB 页面对齐 | 含 `.so` 库 且 targetSdk ≥ Android 15（2025-11-01 后强制）。无 .so 直接跳过 |
| Closed testing 20人×14天 | 仅**新账号**必须；老账号（已有上架应用）可跳过直接 Production |
| Advertising ID 声明 | targetSdk ≥ 33（Android 13）必须；低于则不强制 |
| Photo & video permissions 说明 | 用了 READ_MEDIA_IMAGES 等照片权限才必填 |
| App access 提供测试账号 | 选了 Restricted（需登录）才必须给账号密码 |

### ⬜ 可跳过（完全可选，不影响上架）
- **Internal testing**：提审前内部测几轮，最多 100 人、无需审核。本地测好可跳过
- **Open testing**：让任意用户加入测试收集反馈。可跳过
- **Pre-registration**：上线前造势收集关注。可跳过
- **Managed publishing**：默认 Off（审核通过自动上线），想控制上线时机才开 On

### 🟢 可后续补充/修改（不阻塞首次上架）
- **13 项声明的内容**：上线后随时改（Monitor and improve → Policy and programs → App content），**改声明无需重新打包**，下次发版生效。所以「必须有值」≠「必须一步到位填到完美」
- **Store listing 截图/描述**：随时更新，不影响已上线版本
- **隐私政策页面**：先用可访问链接占位过审，内容后续完善（但内容必须和 Data safety 一致）
- **版本更新**：每次迭代上传 versionCode 更大的 AAB 替换

## 发布轨道

| 轨道 | 是否必须 |
|------|----------|
| Closed testing | 🔴 **新账号必须先做**：20 个测试者 + 连续 14 天，才能解锁 Production |
| Open testing | ⚪ 可跳过 |
| Pre-registration | ⚪ 可跳过 |
| Production | 🔴 最终上架必须走 |

> 老账号（已有上架应用）可跳过测试直接 Production。

## Production 发布步骤

1. Select countries and regions
2. Create a new release → 上传**已签名 AAB**
3. Release name（内部标识，用户看不到，如 `1.0`）
4. Release notes（用户可见，用 locale 标签包裹）：
   ```
   <en-US>
   Initial release. ...
   </en-US>
   ```
5. Preview and confirm（有 Error 必须修）
6. Publishing overview → **Send for review**

## Publishing overview（提交审核最后一步）

汇总所有变更：版本、Store listings、App content、Store settings。
- **Managed publishing = Off（默认）**：审核通过后自动发布
- **Managed publishing = On**：审核通过后需手动点发布（控制上线时机）
- 审核 1–7 天，新账号可能更久。

---

## 签名管理

### 签名信息存入 local.properties（不提交 Git）

```properties
STORE_FILE=/path/to/your/keystore
STORE_PASSWORD=yourPassword
KEY_ALIAS=key0
KEY_PASSWORD=yourPassword
```

`app/build.gradle.kts`：
```kotlin
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) load(f.inputStream())
}
android {
    signingConfigs {
        create("release") {
            storeFile     = file(localProps["STORE_FILE"].toString())
            storePassword = localProps["STORE_PASSWORD"].toString()
            keyAlias      = localProps["KEY_ALIAS"].toString()
            keyPassword   = localProps["KEY_PASSWORD"].toString()
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }
}
```

### 生成 keystore

```bash
keytool -genkeypair \
  -keystore app/photorecovry.jks \
  -alias key0 \
  -keyalg RSA -keysize 2048 -validity 36500 \
  -storepass yourPassword -keypass yourPassword \
  -dname "CN=Name, O=Org, C=CN"
```

### 构建签名 AAB

```bash
./gradlew bundleRelease
# 输出 app/build/outputs/bundle/release/app-release.aab
```

### Play App Signing

首次上传 AAB 时同意 **App signing by Google Play**，Google 自动托管最终签名密钥。

### 签名铁律

- **签名与应用永久绑定**，上线后无法更换（老用户无法升级只能重装）
- **keystore 必须备份**（文件 + storePassword + keyAlias + keyPassword），丢失后无法发更新
- **不要提交 keystore 到 Git**
- 丢失上传密钥：`App signing → Request upload key reset`

---

## 包名 / 应用名修改

### 改包名
1. `app/build.gradle.kts`：`namespace` 与 `applicationId` 同步改
2. `AndroidManifest.xml` 中 `android:name` 类名前缀
3. 批量替换源文件 package/import：`find app/src -name "*.kt" | xargs sed -i '' 's/com.oldpackage/com.newpackage/g'`
4. 重命名源码目录

### 改应用名
- `res/values/strings.xml` 的 `app_name`
- **有多语言资源时（扫描 `strings.has_multiple_locales`）所有语言文件都要同步改**，否则中文系统显示旧名。

---

## 审核状态

| 状态 | 英文 |
|------|------|
| 审核中 | In review |
| 已发布 | Available on Google Play |
| 被拒 | Rejected |
| 被暂停 | Suspended |
