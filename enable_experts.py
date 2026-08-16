# -*- coding: utf-8 -*-
"""
Qoder 专家团自定义模型挂载脚本 v3（通用化：路径/模型自动探测，可移植）
原理：UI 模型列表来自 aicoding.modelConfigs.cache.experts（官方条目默认 disabled）。
      把自定义模型条目注入该列表（enabled=true + C4 strategy enabled），
      UI 即显示且可选；请求层按 custom: 前缀走自定义 API。
前置：patch_qoder_experts.bat 已执行（消除 selectable 时序校验）
用法：1) 完全退出 Qoder
      2) python enable_experts.py [--model <id|displayName|model>] [--list]
         （无 --model 时自动选择第一个自定义模型；--list 列出全部）
      3) 重启 Qoder -> 打开专家团 -> 模型选择器中应出现自定义模型
路径探测（可移植）：--user-dir <Qoder用户目录> 或环境变量 QODER_USER_DIR 优先，
      否则自动使用 %APPDATA%/Qoder。
回滚：rollback_experts.bat
"""
import sqlite3
import json
import shutil
import datetime
import sys
import os
import glob

def detect_user_dir():
    """Qoder 用户数据目录：--user-dir > QODER_USER_DIR > %APPDATA%/Qoder"""
    if "--user-dir" in sys.argv:
        return sys.argv[sys.argv.index("--user-dir") + 1]
    env = os.environ.get("QODER_USER_DIR")
    if env:
        return env
    return os.path.expandvars(r"%APPDATA%\Qoder")

USER_DIR = detect_user_dir()
DB = os.path.join(USER_DIR, "User", "globalStorage", "state.vscdb")
WS_DIR = os.path.join(USER_DIR, "User", "workspaceStorage")
CACHE_KEY = "aicoding.modelConfigs.cache.experts"
CONTEXT_KEY = "1m"  # 上下文大小：1m = 100 万 token（customModels.contextConfig 键名）

TEST_MODE = "--test" in sys.argv
if TEST_MODE:
    DB = sys.argv[sys.argv.index("--test") + 1]


def get_value(cur, key):
    cur.execute("SELECT value FROM ItemTable WHERE key=?", (key,))
    row = cur.fetchone()
    if row is None:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return row[0]


def resolve_model(cur, arg):
    """解析 --model 参数为 customModels 条目：支持 id/displayName/model 精确匹配。
    arg="list" 时列出全部；arg=None 时返回第一个。返回 (target, models)。"""
    cm = get_value(cur, "aicoding.customModels") or []
    if arg == "list":
        print("可用的自定义模型（--model 可传 id/displayName/model）:")
        for m in cm:
            print("  id=%s  model=%s  displayName=%s" % (m.get("id"), m.get("model"), m.get("displayName")))
        return None, cm
    if arg:
        for m in cm:
            if m.get("id") == arg or m.get("displayName") == arg or m.get("model") == arg:
                return m, cm
        print("[!] 未找到模型: %s（用 --list 查看全部）" % arg)
        return None, cm
    if cm:
        return cm[0], cm
    print("[!] aicoding.customModels 为空，请先在 Qoder 中配置自定义模型（第三方 API）。")
    return None, cm


def put_value(cur, key, value):
    cur.execute("SELECT 1 FROM ItemTable WHERE key=?", (key,))
    exists = cur.fetchone() is not None
    payload = json.dumps(value, ensure_ascii=False)
    if exists:
        cur.execute("UPDATE ItemTable SET value=? WHERE key=?", (payload, key))
    else:
        cur.execute("INSERT INTO ItemTable(key, value) VALUES(?,?)", (key, payload))


def build_cache_entry(cm_model):
    """customModels 条目 -> cache.experts 条目格式"""
    cc = cm_model.get("contextConfig") or {}
    tokens = {}
    for k, v in cc.items():
        tokens[k] = {"tokenCount": v.get("tokenCount", 200000), "isDefault": v.get("isDefault", False)}
    tc = cm_model.get("thinkingConfig") or {}
    thinking = {}
    for k, v in tc.items():
        thinking[k] = v if isinstance(v, dict) else {}
    return {
        "name": MODEL_REF,
        "displayName": cm_model.get("displayName") or cm_model.get("model", "Custom"),
        "description": "",
        "format": "openai",
        "source": "custom",
        "multiModalSupported": bool(cm_model.get("is_vl")),
        "reasoningSupported": bool(cm_model.get("is_reasoning")),
        "maxInputTokens": (cc.get("1m") or cc.get("1M") or {}).get("tokenCount", 1000000),
        "enabled": True,
        "originalPriceFactor": 0,
        "priceFactor": 1,
        "isDefault": True,
        "isNew": False,
        "excludeTags": None,
        "tags": None,
        "icon": None,
        "strategies": [{"tag": "C4", "enabled": True, "disabled_message_key": "", "priority": 999}],
        "contextConfig": tokens or {"200K": {"tokenCount": 200000, "isDefault": True}},
        "thinkingConfig": thinking,
        "isEditable": True,
    }


def cleanup_session_memory(ts, sel_key):
    """清理所有库中的 session 模型记忆与旧 selector（防旧会话恢复覆盖模型）"""
    if TEST_MODE:
        return 0  # dry-run 不碰真实 workspace 库
    dbs = [DB] + glob.glob(os.path.join(WS_DIR, "*", "state.vscdb"))
    removed = 0
    for db in dbs:
        if not os.path.exists(db):
            continue
        shutil.copy2(db, db + ".bak_experts_v3_" + ts)
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT key FROM ItemTable WHERE key LIKE 'chat.modelConfig.session.%'")
        keys = [r[0] for r in cur.fetchall()]
        for k in keys:
            cur.execute("DELETE FROM ItemTable WHERE key=?", (k,))
            removed += 1
        if db == DB:
            # 主库：删除其他模型的 experts selector 残留（保留当前模型的）
            cur.execute("SELECT key FROM ItemTable WHERE key LIKE 'aicoding.modelSelector.runtimeConfig.experts.%' AND key != ?", (sel_key,))
            for (k,) in cur.fetchall():
                cur.execute("DELETE FROM ItemTable WHERE key=?", (k,))
        conn.commit()
        conn.close()
    return removed


def main():
    # 模型解析：--list / --model <id|displayName|model> / 默认第一个
    arg = "list" if "--list" in sys.argv else None
    if "--model" in sys.argv:
        arg = sys.argv[sys.argv.index("--model") + 1]

    # --list 为只读操作，允许 Qoder 运行中执行
    if arg == "list":
        if not os.path.exists(DB):
            print("[!] 找不到配置库:", DB)
            sys.exit(2)
        conn = sqlite3.connect(DB)
        resolve_model(conn.cursor(), "list")
        conn.close()
        sys.exit(0)

    if not TEST_MODE:
        tasklist = os.popen('tasklist /FO CSV /NH 2>nul').read().lower()
        if "qoder" in tasklist:
            print("[!] Qoder 仍在运行，请先完全退出（含托盘）再执行。")
            sys.exit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = DB + ".bak_experts_v3_" + ts
    shutil.copy2(DB, bak)
    print("[1/6] 已备份主库:", os.path.basename(bak))

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 2) 前置校验：目标模型存在
    target, _cm = resolve_model(cur, arg)
    if not target:
        conn.close()
        sys.exit(2)
    CUSTOM_MODEL_ID = target["id"]
    MODEL_REF = "custom:" + CUSTOM_MODEL_ID
    SEL_KEY = "aicoding.modelSelector.runtimeConfig.experts." + MODEL_REF
    print("[2/6] 目标模型:", target.get("displayName"), "/", target.get("model"))

    # 3) 注入 cache.experts（按 name 去重追加）
    cache = get_value(cur, CACHE_KEY) or []
    if not isinstance(cache, list):
        cache = []
    old_names = [m.get("name") for m in cache]
    if MODEL_REF in old_names:
        print("[3/5] cache.experts 已存在 %s，更新 enabled 状态" % MODEL_REF)
        cache = [m for m in cache if m.get("name") != MODEL_REF]
    entry = build_cache_entry(target)
    cache.append(entry)
    put_value(cur, CACHE_KEY, cache)

    # 4) 模型配置与选择器 + 清理 session 记忆
    put_value(cur, "chat.modelConfig.experts", MODEL_REF)
    put_value(cur, SEL_KEY, {"contextKey": CONTEXT_KEY})
    # 4.5) customModels 默认档位改为 1m（UI 上下文默认显示 1M）
    cm_all = get_value(cur, "aicoding.customModels") or []
    cc_changed = 0
    for m in cm_all:
        if m.get("id") == CUSTOM_MODEL_ID:
            cc = m.get("contextConfig") or {}
            for k, v in cc.items():
                v["isDefault"] = (str(k).lower() == CONTEXT_KEY.lower())
            cc_changed = 1
    if cc_changed:
        put_value(cur, "aicoding.customModels", cm_all)
    conn.commit()
    removed = cleanup_session_memory(ts, SEL_KEY)
    print("[4/6] 已清理 %d 条 session 模型记忆（含旧会话残留）" % removed)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 5) 读回验证
    exp = get_value(cur, CACHE_KEY) or []
    entry_ok = any(m.get("name") == MODEL_REF and m.get("enabled") for m in exp)
    cfg_ok = get_value(cur, "chat.modelConfig.experts") == MODEL_REF
    sel_ok = (get_value(cur, SEL_KEY) or {}).get("contextKey") == CONTEXT_KEY
    cm2 = get_value(cur, "aicoding.customModels") or []
    cc_ok = any(m.get("id") == CUSTOM_MODEL_ID and (m.get("contextConfig") or {}).get(CONTEXT_KEY, {}).get("isDefault") for m in cm2)
    conn.close()

    print("[5/6] cache.experts 条目数:", len(exp), "| 注入成功:", entry_ok)
    print("       modelConfig:", cfg_ok, "| selector:", sel_ok, "| 1m默认:", cc_ok)
    if entry_ok and cfg_ok and sel_ok and cc_ok:
        print("[6/6] 全部通过。重启 Qoder 打开专家团：默认使用所选自定义模型，不会再被旧会话覆盖。")
        print("      失败可回滚：rollback_experts.bat")
    else:
        print("[6/6] 验证未全通过！请勿重启，先运行 rollback_experts.bat 恢复。")


if __name__ == "__main__":
    main()
