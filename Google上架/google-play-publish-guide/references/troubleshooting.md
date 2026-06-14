# 常见错误 & 英文提示翻译

## 发布报错对照表

| 错误信息 | 原因 | 解决 |
|----------|------|------|
| All uploaded bundles must be signed | 上传了未签名 AAB | 用 release 签名配置重构建 |
| All developers requesting access to the photo and video permissions... | 未填照片权限核心功能说明 | App content → Photo and video permissions 填写（≤250 字符） |
| Incomplete advertising ID declaration | 未声明是否用广告 ID（targetSdk≥33 必须） | App content → Advertising ID 选 Yes/No，**无需重新打包** |
| This APK will not be served... completely shadowed by one or more APKs with higher version codes | Release 同时含新旧两个包，旧版被新版覆盖 | Edit release → App bundles 列表移除旧版本号包，只留最新 |
| APK is not aligned on a 16KB boundary / files not aligned on a 16KB page size boundary | 未 16KB 对齐（Android 15+ 强制） | 见 references/16kb-alignment.md |

## 替换已上传的包（不等 quick check 跑完）

1. Test and release → Production（或对应轨道）→ Edit release
2. App bundles 区上传新 AAB
3. 移除旧版本号包
4. 保存 → Publishing overview → Send for review

> 新包 `versionCode` 必须 > 旧包，否则无法上传。App content 声明属后台配置，改了无需重新打包。

## 英文提示翻译

| 英文 | 中文 |
|------|------|
| You have unresolved issues | 你有未解决的问题 |
| Complete the following steps | 请完成以下步骤 |
| This field is required | 此字段必填 |
| Your app has been rejected | 应用被拒 |
| Policy violation | 政策违规 |
| Deceptive behavior | 欺骗行为 |
| Intellectual property | 知识产权问题 |
| Limited functionality | 功能不完整 |
| Send for review | 提交审核 |
| Managed publishing | 手动控制发布时机（关闭时审核通过自动发布） |
| Publishing overview | 发布概览 |
