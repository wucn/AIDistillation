#!/usr/bin/env python3
"""
扫描 Android 项目，输出一份「结构化的项目事实清单」（JSON 到 stdout）。
这份清单会被 SKILL.md 用来映射到 Google Play Console 各声明项的取舍依据。

只做「事实采集」：找到了什么 SDK、有没有 .so、targetSdk 是多少。
不做判断（判断由调用方 / 大模型根据 references/ 完成）。

用法：
    python3 scan_project.py /path/to/android/project
"""
import json
import os
import re
import sys
import glob


# ---- 已知 SDK 识别表 -------------------------------------------------
# key = 依赖字符串里要匹配的子串（小写）；value = 该 SDK 涉及的数据维度
# 数据维度含义见 references/console-declarations.md 的 Data safety 章节
KNOWN_SDKS = {
    # 广告 SDK —— 触发 Ads=Yes, Advertising ID=Yes, Device or other IDs, Advertising
    "play-services-ads": {"type": "ad", "label": "Google Mobile Ads / AdMob"},
    "google.ads": {"type": "ad", "label": "Google Mobile Ads / AdMob"},
    "user-messaging-platform": {"type": "ad", "label": "Google UMP (广告同意)"},
    "com.anythink": {"type": "ad", "label": "TopOn / Anythink 聚合广告"},
    "pangle": {"type": "ad", "label": "Pangle / 穿山甲"},
    "ironsource": {"type": "ad", "label": "ironSource"},
    "unity3d.ads": {"type": "ad", "label": "Unity Ads"},
    "com.mintegral": {"type": "ad", "label": "Mintegral"},
    "vungle": {"type": "ad", "label": "Vungle / Liftoff"},
    "applovin": {"type": "ad", "label": "AppLovin / MAX"},
    "adcolony": {"type": "ad", "label": "AdColony"},
    "chartboost": {"type": "ad", "label": "Chartboost"},
    "com.qq.e": {"type": "ad", "label": "优量汇 / GDT"},
    # 归因 / 分析
    "firebase-analytics": {"type": "analytics", "label": "Firebase Analytics"},
    "firebase-crashlytics": {"type": "crash", "label": "Firebase Crashlytics"},
    "com.google.firebase": {"type": "firebase", "label": "Firebase (通用)"},
    "appsflyer": {"type": "attribution", "label": "AppsFlyer 归因"},
    "com.adjust.sdk": {"type": "attribution", "label": "Adjust 归因"},
    "adjust": {"type": "attribution", "label": "Adjust 归因"},
    "kochava": {"type": "attribution", "label": "Kochava 归因"},
    "branch": {"type": "attribution", "label": "Branch"},
    "com.facebook": {"type": "facebook", "label": "Facebook SDK"},
    "com.umeng": {"type": "analytics", "label": "友盟 Umeng"},
    "umeng": {"type": "analytics", "label": "友盟 Umeng"},
    "flurry": {"type": "analytics", "label": "Flurry"},
    "amplitude": {"type": "analytics", "label": "Amplitude"},
    "mixpanel": {"type": "analytics", "label": "Mixpanel"},
    "sentry": {"type": "crash", "label": "Sentry"},
    "bugly": {"type": "crash", "label": "腾讯 Bugly"},
    "sensorsdata": {"type": "analytics", "label": "神策 Sensors Analytics"},
}

# 与照片 / 媒体权限声明（5.8 Photo and video permissions）相关的权限
PHOTO_VIDEO_PERMS = {
    "READ_MEDIA_IMAGES",
    "READ_MEDIA_VIDEO",
    "READ_MEDIA_VISUAL_USER_SELECTED",
    "READ_EXTERNAL_STORAGE",
    "WRITE_EXTERNAL_STORAGE",
    "MANAGE_MEDIA",
    "MANAGE_EXTERNAL_STORAGE",
    "ACCESS_MEDIA_LOCATION",
}


def parse_version_catalog(root):
    """解析 gradle/libs.versions.toml 的 [versions] 段为 dict。

    版本目录（version catalog）是 sdk 版本与 AGP 版本的权威来源。
    很多项目把 compileSdk/minSdk/targetSdk/agp 写在这里，build.gradle.kts 里
    用 libs.versions.X.get() 引用 —— 不解析这个，就会把这些字段读成 null/错值。
    用纯正则解析（Python 3.9 没有内置 tomllib）。
    """
    toml_path = None
    for cand in glob.glob(os.path.join(root, "**", "libs.versions.toml"), recursive=True):
        # 优先 gradle/ 下的主 catalog
        if os.sep + "gradle" + os.sep in cand:
            toml_path = cand
            break
        toml_path = toml_path or cand
    if not toml_path:
        return {"path": None, "versions": {}}
    text = read(toml_path)
    versions = {}
    # 只取 [versions] 段；遇到下一个 [...] section 停止
    in_versions = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_versions = stripped.lower().startswith("[versions]")
            continue
        if not in_versions:
            continue
        # key = "value"   或   key = { ... }
        m = re.match(r'^([A-Za-z0-9_\-]+)\s*=\s*"([^"]+)"', stripped)
        if m:
            versions[m.group(1)] = m.group(2)
            continue
        m = re.match(r'^([A-Za-z0-9_\-]+)\s*=\s*\{[^}]*version\s*=\s*"([^"]+)"', stripped)
        if m:
            versions[m.group(1)] = m.group(2)
    return {"path": toml_path, "versions": versions}


def resolve_ref(expr, catalog):
    """把 libs.versions.X.get() / libs.findVersion("X") 形式的引用解析成 catalog 值。"""
    if not expr:
        return None
    m = re.search(r"libs\.versions\.([A-Za-z0-9_\-]+)\.get\(\)", expr)
    if not m:
        m = re.search(r'libs\.findVersion\(["\']([A-Za-z0-9_\-]+)["\']\)', expr)
    if m:
        return catalog.get(m.group(1))
    return None


def find_files(root, patterns):
    hits = []
    for pat in patterns:
        hits.extend(glob.glob(os.path.join(root, "**", pat), recursive=True))
    return hits


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def extract_gradle_info(root, catalog):
    """从 app/build.gradle(.kts) 提取 applicationId / sdk / version 等。

    会解析版本目录引用：build.gradle.kts 里常写
        minSdk = libs.versions.minSdk.get().toInt()
    此时直接 grep 数字会落空，必须从 catalog 解析。versionCode/versionName
    若是函数或表达式（calculateVersionCode() / 引用变量），标记 computed=true，
    避免把占位值当真值上报。
    """
    versions = catalog.get("versions", {})
    info = {}
    candidates = find_files(root, ["build.gradle", "build.gradle.kts"])
    # 优先 app 模块下的
    app_gradles = [c for c in candidates if os.sep + "app" + os.sep in c + os.sep] or candidates
    blob = ""
    gradle_files = []
    for g in app_gradles:
        text = read(g)
        blob += "\n" + text
        gradle_files.append(g)

    def raw_after(keyword_patterns):
        """取 keyword= 后面到行尾的原始表达式（用于判断是不是引用/公式）。"""
        for p in keyword_patterns:
            m = re.search(p + r"\s*[=:]\s*(.+?)\s*(?://.*)?$", blob, re.MULTILINE)
            if m:
                return m.group(1).strip().rstrip(",")
        return None

    def first_value(patterns):
        for p in patterns:
            m = re.search(p, blob, re.IGNORECASE)
            if m:
                return m.group(1).strip().strip('"').strip("'")
        return None

    # applicationId / namespace：字符串字面量
    info["applicationId"] = first_value([r"applicationId\s*[=:]?\s*['\"]([^'\"]+)"])
    info["namespace"] = first_value([r"namespace\s*=\s*['\"]([^'\"]+)"])

    # sdk 版本：先看是不是 catalog 引用，再看字面量，再看 catalog 同名 key 兜底
    for field, lit_p, cat_key in [
        ("minSdk", r"minSdk\s*=\s*(\d+)", "minSdk"),
        ("targetSdk", r"targetSdk\s*=\s*(\d+)", "targetSdk"),
        ("compileSdk", r"compileSdk\s*=\s*(\d+)", "compileSdk"),
    ]:
        raw = raw_after([field])
        resolved = resolve_ref(raw, versions) if raw else None
        if resolved:
            info[field] = resolved
        else:
            v = first_value([lit_p, field + r"Version\s+(\d+)"])
            info[field] = v or versions.get(cat_key)

    # versionCode / versionName：可能是数字/字符串，也可能是函数或变量 → 标 computed
    vc_raw = raw_after(["versionCode"])
    info["versionCode"] = _resolve_version_value(vc_raw, versions, numeric=True)
    vn_raw = raw_after(["versionName"])
    info["versionName"] = _resolve_version_value(vn_raw, versions, numeric=False)

    info["gradle_files_read"] = gradle_files
    return info, blob


def _resolve_version_value(raw, catalog, numeric):
    """versionCode/versionName 可能是字面量、catalog 引用、函数调用或变量。
    返回 dict：{value, computed}。computed=true 时 value 是原始表达式，仅供提示。"""
    out = {"value": None, "computed": False}
    if not raw:
        return out
    ref = resolve_ref(raw, catalog)
    if ref is not None:
        out["value"] = ref
        return out
    # 字面量数字
    if numeric:
        m = re.match(r"^(\d+)\s*(?:[+\-*/].*)?$", raw)
        if m:
            out["value"] = m.group(1)
            if any(c in raw for c in "+-*/"):
                out["computed"] = True  # 如 10003 + abiCode
            return out
    else:
        m = re.match(r'^["\']([^"\']+)["\']', raw)
        if m:
            out["value"] = m.group(1)
            return out
    # 否则视为函数/变量（calculateVersionCode()、appVersionName 等）
    out["value"] = raw
    out["computed"] = True
    return out


def extract_agp_version(root, catalog=None):
    """AGP 版本决定是否默认支持 16KB 页面对齐（8.5.1+ 默认支持）。

    取值优先级：
      1. 版本目录 libs.versions.toml 的 agp = "x.y.z"（最权威，且不会被子模块干扰）
      2. 根 build.gradle(.kts) 的 plugins 块 id("com.android.application") version "x.y.z"
      3. settings.gradle(.kts) 的 pluginManagement
    注意：不能扫所有 build.gradle —— 子模块可能 compileOnly 一个旧版
    com.android.tools.build:gradle（如 SensorsData 插件工程），会污染结果。
    """
    # 1. catalog
    if catalog and catalog.get("versions", {}).get("agp"):
        return catalog["versions"]["agp"]
    # 2/3. 只读根目录的 build.gradle / settings.gradle（排除子模块）
    root_files = [os.path.join(root, n) for n in
                  ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")
                  if os.path.isfile(os.path.join(root, n))]
    blob = "\n".join(read(c) for c in root_files)
    m = (re.search(r'com\.android\.application.{0,60}?version\s*["\']([\d.]+)["\']', blob) or
         re.search(r"com\.android\.tools\.build:gradle[:\s]*[\"]?([\d.]+)", blob))
    return m.group(1) if m else None


def find_use_legacy_packaging(root):
    blob = ""
    for g in find_files(root, ["build.gradle", "build.gradle.kts"]):
        blob += read(g)
    has = "useLegacyPackaging" in blob
    val = None
    if has:
        m = re.search(r"useLegacyPackaging\s*(?:=|\s)\s*(true|false)", blob)
        val = m.group(1) if m else "true"
    return {"present": has, "value": val}


def find_signing_config(root):
    """是否已配置 release 签名信息。"""
    app_gradles = [c for c in find_files(root, ["build.gradle", "build.gradle.kts"])
                   if os.sep + "app" + os.sep in c + os.sep]
    blob = "\n".join(read(g) for g in (app_gradles or []))
    has_signing_block = "signingConfigs" in blob
    has_release_signed = bool(re.search(r"release\s*\{[^}]*signingConfig", blob, re.DOTALL))
    uses_local_props = "local.properties" in blob or "STORE_FILE" in blob
    return {
        "has_signing_config_block": has_signing_block,
        "release_signed": has_release_signed,
        "uses_local_properties": uses_local_props,
    }


def find_native_libs(root):
    """找 .so 文件 —— 决定是否需要 16KB 页面对齐。"""
    so_files = find_files(root, ["*.so"])
    # 过滤掉 build 缓存里可能的重复，但保留以提示来源
    so_files = [s for s in so_files if os.path.isfile(s)]
    # 按 abi 分组
    by_abi = {}
    for s in so_files:
        parts = s.split(os.sep)
        abi = next((p for p in parts if p in ("armeabi-v7a", "arm64-v8a", "x86", "x86_64", "armeabi", "riscv64")), "unknown")
        by_abi.setdefault(abi, []).append(s)
    return {"count": len(so_files), "by_abi": {k: len(v) for k, v in by_abi.items()}, "has_native_libs": len(so_files) > 0}


def find_permissions(root):
    manifests = find_files(root, ["AndroidManifest.xml"])
    blob = "\n".join(read(m) for m in manifests)
    perms = re.findall(r'uses-permission[^>]*android:name\s*=\s*["\']([^"\']+)["\']', blob)
    perms = [p for p in perms if p]
    short = sorted({p.split(".")[-1] for p in perms})
    photo_related = sorted({p.split(".")[-1] for p in perms if p.split(".")[-1] in PHOTO_VIDEO_PERMS})
    internet = "INTERNET" in short
    return {
        "manifest_files": manifests,
        "all_permissions_short": short,
        "photo_video_related": photo_related,
        "has_internet": internet,
    }


def find_sdks(root):
    """扫描依赖声明识别已知 SDK。"""
    blobs = []
    for pat in ["build.gradle", "build.gradle.kts", "libs.versions.toml", "build.gradle", "build.gradle.files"]:
        pass
    dep_files = find_files(root, ["build.gradle", "build.gradle.kts", "libs.versions.toml", "pom.xml"])
    blob = "\n".join(read(f) for f in dep_files)
    # 也扫源码里的 import / 包名，弥补纯字符串匹配
    src_blob = ""
    for s in find_files(root, ["*.kt", "*.java"])[:2000]:
        src_blob += "\n" + read(s)
    haystack = (blob + "\n" + src_blob).lower()

    found = {}
    for needle, meta in KNOWN_SDKS.items():
        if needle.lower() in haystack:
            found[needle] = meta["label"]

    def has_any(substrs):
        return any(s in haystack for s in substrs)

    categories = {
        "has_ad_sdk": has_any(["play-services-ads", "google.ads", "com.anythink", "pangle",
                               "ironsource", "unity3d.ads", "com.mintegral", "vungle",
                               "applovin", "adcolony", "chartboost", "com.qq.e"]),
        "has_analytics_sdk": has_any(["firebase-analytics", "amplitude", "mixpanel", "com.umeng", "umeng",
                                      "flurry", "sensorsdata"]),
        "has_crash_sdk": has_any(["crashlytics", "sentry", "bugly"]),
        "has_attribution_sdk": has_any(["appsflyer", "com.adjust.sdk", "adjust", "kochava", "branch"]),
        "has_firebase": has_any(["com.google.firebase", "firebase"]),
        "has_facebook_sdk": has_any(["com.facebook"]),
    }
    return {"detected_sdks": found, **categories}


def find_login_signals(root):
    """粗略判断是否有登录功能 —— 影响 App access (5.2)。不可靠，仅作提示。"""
    src = ""
    for pat in ["*.kt", "*.java"]:
        for s in find_files(root, [pat])[:2000]:
            src += "\n" + read(s)
    low = src.lower()
    signals = {
        "keywords_login": bool(re.search(r"\b(login|signin|sign_in|authenticate|jwt|accesstoken|/login)\b", low)),
        "uses_account_manager": "AccountManager" in src,
    }
    # 也看 manifest 是否声明了登录相关 activity
    manifests = find_files(root, ["AndroidManifest.xml"])
    mblob = "\n".join(read(m) for m in manifests).lower()
    signals["login_activity_in_manifest"] = bool(re.search(r"(login|signin)", mblob))
    signals["uncertain"] = True  # 提醒调用方：机器判断不可靠，需人工确认
    return signals


def find_store_assets(root):
    """找现成的商店素材（图标、截图、feature graphic），方便评估商店详情页就绪度。"""
    res = find_files(root, ["ic_launcher*.png", "ic_launcher*.xml"])
    screenshots = []
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        for s in glob.glob(os.path.join(root, "**", "screenshots"), recursive=True):
            screenshots.append(s)
        screenshots += [p for p in glob.glob(os.path.join(root, "**", "*screenshot*"), recursive=True)
                        if p.lower().endswith((".png", ".jpg", ".jpeg"))]
    return {
        "launcher_icons": res[:10],
        "screenshots_found": len(set(screenshots)) > 0,
    }


def find_app_name_and_locales(root):
    """读 strings.xml 的 app_name 和多语言目录。"""
    strings_files = find_files(root, ["strings.xml"])
    locales = sorted({os.path.basename(os.path.dirname(f)) for f in strings_files})
    app_name = None
    for f in strings_files:
        text = read(f)
        m = re.search(r'<string\s+name="app_name"[^>]*>([^<]+)</string>', text)
        if m:
            app_name = m.group(1).strip()
            break
    return {
        "app_name": app_name,
        "locale_value_dirs": locales,
        "has_multiple_locales": len(locales) > 1,
        "strings_files": strings_files,
    }


def main():
    if len(sys.argv) < 2:
        print("usage: scan_project.py /path/to/project", file=sys.stderr)
        sys.exit(1)
    root = os.path.abspath(sys.argv[1])
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        sys.exit(1)

    catalog = parse_version_catalog(root)
    gradle_info, gradle_blob = extract_gradle_info(root, catalog)
    result = {
        "project_root": root,
        "version_catalog": catalog["path"],
        "gradle": gradle_info,
        "agp_version": extract_agp_version(root, catalog),
        "packaging": find_use_legacy_packaging(root),
        "signing": find_signing_config(root),
        "native_libs": find_native_libs(root),
        "permissions": find_permissions(root),
        "sdks": find_sdks(root),
        "login_signals": find_login_signals(root),
        "store_assets": find_store_assets(root),
        "strings": find_app_name_and_locales(root),
    }

    # 派生结论（仍然只是事实层面的布尔判断，不含 Play Console 取值）
    s = result["sdks"]
    n = result["native_libs"]
    p = result["permissions"]
    target = gradle_info.get("targetSdk")
    try:
        target_int = int(str(target)) if target else None
    except ValueError:
        target_int = None
    result["derived"] = {
        "needs_16kb_check": n["has_native_libs"],
        "agp_supports_16kb_default": _agp_ok(result["agp_version"]),
        "must_declare_advertising_id": target_int is not None and target_int >= 33,
        "likely_has_ads": s["has_ad_sdk"],
        "likely_collects_device_ids": s["has_ad_sdk"] or s["has_analytics_sdk"]
                                      or s["has_attribution_sdk"] or s["has_facebook_sdk"],
        "has_photo_video_perms": bool(p["photo_video_related"]),
        "release_signing_ready": result["signing"]["release_signed"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _agp_ok(v):
    if not v:
        return None
    try:
        parts = v.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
        if (major, minor) > (8, 5):
            return True
        if (major, minor) == (8, 5) and patch >= 1:
            return True
        return False
    except Exception:
        return None


if __name__ == "__main__":
    main()
