# 16KB 页面对齐（Android 15+）

自 **2025-11-01** 起，提交 Google Play 且 targetSdk 为 Android 15+ 的应用更新，**必须支持 16KB 页面大小**。

## 是否需要适配？

```
if (项目没有 .so 动态库)  → 无须适配，纯 Kotlin/Java 自动兼容
else                       → 需要适配
```

扫描器 `native_libs.has_native_libs` 给出答案。**注意**：即使自己代码没用 .so，第三方 SDK（广告/地图/Firebase 等）可能含 .so，必须查。

## 判断依据（来自扫描结果）

| 扫描字段 | 含义 |
|----------|------|
| `native_libs.has_native_libs` = false | 无 .so → 无须处理，直接跳过本节 |
| `native_libs.has_native_libs` = true | 需检查对齐 |
| `derived.agp_supports_16kb_default` = true | AGP ≥ 8.5.1，默认已对齐（最省事） |
| `derived.agp_supports_16kb_default` = false | AGP < 8.5.1，需手动配置或升级 |
| `derived.agp_supports_16kb_default` = null | AGP 版本未识别到，**需人工确认** |
| `packaging.value` = true | 已设 `useLegacyPackaging=true`（临时绕过方案，有解压开销，不推荐长期） |

## 检查 APK 是否符合

```bash
zipalign -c -P 16 -v 4 your_app.apk
# 或
bundletool validate-bundle --bundle=your_app.aab
```

Android Studio：Build → Analyze APK → 看 lib 文件夹对齐列显示 "16KB"。

## 解决方案（按优先级）

### 方案一：升级 AGP 到 8.5.1+（推荐）
AGP 8.5.1+ 默认自动 16KB 对齐。

### 方案二：Gradle 配置（AGP ≤ 8.5）
Kotlin DSL：
```kotlin
android {
    packaging {
        jniLibs { useLegacyPackaging = true }
    }
}
```
Groovy：
```gradle
android {
    packagingOptions {
        jniLibs { useLegacyPackaging true }
    }
}
```
> ⚠️ 会压缩 .so 增加启动解压开销，不建议长期用，正确做法是升级 AGP 或重编 .so。

### 方案三：重编自己的 .so（NDK r28+ 默认对齐）
NDK r27 需：
- ndk-build（Application.mk）：`APP_SUPPORT_FLEXIBLE_PAGE_SIZES := true`
- CMake：`arguments += listOf("-DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON")`

### 方案四：更新第三方 SDK
大厂 SDK 等官方更新后升级；小团队联系作者；无法更新则移除功能或换库。

## 测试

1. Android Studio 最新版 + 下载 Android 15 (API 35)
2. 勾选含 "16K Page Size" 的 System Image 建模拟器
3. 跑含 .so 的功能，看是否崩溃

## 完整流程

```
检查是否有 .so  →  无则跳过
              ↓ 有
确认来源（自己 vs 第三方）
              ↓
选方案：升级 AGP / 更新 SDK / 重编 .so / 临时 useLegacyPackaging
              ↓
重构建 → zipalign 验证 → 16KB 模拟器测试 → 上传
```

参考：https://developer.android.com/guide/practices/page-sizes
