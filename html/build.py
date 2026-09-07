# -*- coding: utf-8 -*-
"""把 core.js + 封面图内嵌进 template.html,生成单文件 html。"""
import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(HERE, "core.js")
TEMPLATE = os.path.join(HERE, "template.html")
COVER = os.path.join(HERE, "..", "py", "assets", "default_cover.png")
OUT = os.path.join(HERE, "png伪装工具.html")


def main():
    core_js = open(CORE, encoding="utf-8").read()
    template = open(TEMPLATE, encoding="utf-8").read()
    b64 = ""
    if os.path.isfile(COVER):
        with open(COVER, "rb") as f:
            b64 = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    html = template.replace("/*__CORE_JS__*/", core_js).replace("/*__COVER_B64__*/", b64)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成:", OUT, os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    main()
