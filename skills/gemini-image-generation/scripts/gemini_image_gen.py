# -*- coding: utf-8 -*-
"""
Gemini Nano Banana 图像生成模块（电商 skill 生图 L1 能力）
================================================================
底层模型：Google Gemini 2.5 Flash Image（Nano Banana）
API Key ：从环境变量 GOOGLE_API_KEY 读取；skill 文件内一律使用占位符 ${GOOGLE_API_KEY}
          严禁把明文 Key 写进任何 skill / 脚本 / 配置文件中。

用法示例：
    python gemini_image_gen.py --prompt "..." --output "D:/out/main.png" [--aspect 1:1] [--model gemini-2.5-flash-image]
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error

DEFAULT_MODEL = "gemini-2.5-flash-image"  # Nano Banana
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 支持的宽高比 -> Gemini API aspectRatio 参数
ASPECT_MAP = {
    "1:1": "1:1",
    "16:9": "16:9",
    "9:16": "9:16",
    "4:3": "4:3",
    "3:4": "3:4",
}


def get_api_key():
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key or key.startswith("${"):
        sys.stderr.write(
            "[ERROR] 未检测到有效的 GOOGLE_API_KEY。\n"
            "请在环境变量中配置 Google AI Studio 免费 Key（https://aistudio.google.com/apikey），"
            "或用占位符 ${GOOGLE_API_KEY} 由运行时注入。\n"
        )
        sys.exit(2)
    return key


def generate(prompt, output_path, aspect_ratio="1:1", model=DEFAULT_MODEL, timeout=120):
    key = get_api_key()
    ratio = ASPECT_MAP.get(aspect_ratio, "1:1")
    url = API_BASE.format(model=model) + "?key=" + key

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": ratio},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        sys.stderr.write(f"[ERROR] Gemini API HTTP {e.code}: {body}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"[ERROR] 请求失败: {e}\n")
        sys.exit(1)

    # 提取生成的图片（inlineData）
    image_bytes = None
    mime = "image/png"
    try:
        for part in data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                image_bytes = base64.b64decode(part["inlineData"]["data"])
                mime = part["inlineData"].get("mimeType", "image/png")
                break
    except (KeyError, IndexError, TypeError):
        pass

    if image_bytes is None:
        # 检查是否有阻塞/错误信息
        try:
            finish = data["candidates"][0].get("finishReason", "")
            msg = data.get("promptFeedback", {}).get("blockReason", "")
        except (KeyError, IndexError):
            finish, msg = "", ""
        sys.stderr.write(
            f"[ERROR] 未返回图片。finishReason={finish}, blockReason={msg}\n"
            f"原始返回: {json.dumps(data, ensure_ascii=False)[:800]}\n"
        )
        sys.exit(1)

    # 根据 mime 确定扩展名
    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    out = output_path
    if not os.path.splitext(out)[1]:
        out += ext_map.get(mime, ".png")

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(image_bytes)
    print(f"[OK] 图片已保存: {out} ({len(image_bytes)} bytes, {mime})")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Gemini Nano Banana 生图")
    ap.add_argument("--prompt", required=True, help="图像描述（英文效果更佳）")
    ap.add_argument("--output", required=True, help="输出文件路径（如 D:/out/main.png）")
    ap.add_argument("--aspect", default="1:1", help="宽高比：1:1 / 16:9 / 9:16 / 4:3 / 3:4")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="模型名，默认 gemini-2.5-flash-image")
    ap.add_argument("--timeout", type=int, default=120, help="请求超时（秒）")
    args = ap.parse_args()
    generate(args.prompt, args.output, args.aspect, args.model, args.timeout)
