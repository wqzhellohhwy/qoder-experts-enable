# -*- coding: utf-8 -*-
"""
Qoder 禁用自动更新脚本
原理：Qoder 更新会覆盖 Program Files 中的 experts patch（已实证 2026-08-15 12:25 更新还原）。
      修改两处配置关闭自动更新：
        1) User/settings.json   -> app.configAdvancedAutoUpdate = false
        2) User/app.json        -> config.advanced.autoUpdate = false
用法：1) 完全退出 Qoder
      2) 双击 disable_autoupdate.bat
      3) 重启 Qoder（自动更新已关闭，patch 不会再被覆盖）
恢复：手动把两个文件中的 false 改回 true，或运行 restore_autoupdate.bat
路径探测（可移植）：--user-dir <Qoder用户目录> 或环境变量 QODER_USER_DIR 优先，
      否则自动使用 %APPDATA%/Qoder。
"""
import os
import sys
import json
import shutil
import datetime

def detect_base():
    """Qoder 用户配置目录（含 settings.json/app.json）：--user-dir > QODER_USER_DIR > %APPDATA%/Qoder"""
    if "--user-dir" in sys.argv:
        return os.path.join(sys.argv[sys.argv.index("--user-dir") + 1], "User")
    env = os.environ.get("QODER_USER_DIR")
    if env:
        return os.path.join(env, "User")
    return os.path.join(os.path.expandvars(r"%APPDATA%\Qoder"), "User")

BASE = detect_base()
TARGETS = [
    (os.path.join(BASE, "settings.json"), ["app", "configAdvancedAutoUpdate"]),
    (os.path.join(BASE, "app.json"), ["config", "advanced", "autoUpdate"]),
]

TEST_MODE = "--test" in sys.argv
if TEST_MODE:
    # 测试模式：用工作区副本
    wd = os.path.dirname(os.path.abspath(__file__))
    TARGETS = [
        (os.path.join(wd, "_t_settings.json"), ["app", "configAdvancedAutoUpdate"]),
        (os.path.join(wd, "_t_app.json"), ["config", "advanced", "autoUpdate"]),
    ]


def get_path(obj, path):
    for k in path:
        if not isinstance(obj, dict) or k not in obj:
            return None
        obj = obj[k]
    return obj


def set_path(obj, path, value):
    for k in path[:-1]:
        obj = obj.setdefault(k, {})
    obj[path[-1]] = value


def main():
    if not TEST_MODE:
        tasklist = os.popen('tasklist /FO CSV /NH 2>nul').read().lower()
        if "qoder" in tasklist:
            print("[!] Qoder 仍在运行，请先完全退出再执行（否则配置会被覆盖）。")
            sys.exit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ok = True
    for path, keys in TARGETS:
        if not os.path.exists(path):
            print("[!] 不存在:", path)
            ok = False
            continue
        bak = path + ".bak_noautoupdate_" + ts
        shutil.copy2(path, bak)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        old = get_path(data, keys)
        if old is None:
            print("[!] %s 未找到配置 %s，跳过" % (os.path.basename(path), ".".join(keys)))
            ok = False
            continue
        set_path(data, keys, False)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 读回验证
        with open(path, "r", encoding="utf-8") as f:
            check = json.load(f)
        new = get_path(check, keys)
        print("[%s] %s: %s -> %s（备份: %s）" % (
            "OK" if new is False else "FAIL",
            os.path.basename(path), old, new, os.path.basename(bak)))
        if new is not False:
            ok = False

    if ok:
        print("全部完成。Qoder 自动更新已关闭，重启后生效。")
    else:
        print("部分失败，请检查上述输出。")


if __name__ == "__main__":
    main()
