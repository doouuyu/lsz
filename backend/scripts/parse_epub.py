"""
解析《本草纲目》epub，提取结构化药物条目。

策略：用「药名《来源》」+ 后续存在【释名/集解/气味/主治】来定位所有药材条目。

输出：
  backend/data/bencao_fulltext.txt  - 全文
  backend/data/bencao_parsed.json   - 结构化条目
"""

import json
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path


# ===== 古今药名对照（常用） =====
HERB_NAME_ALIASES = {
    "黄耆": "黄芪",
    "赤箭": "天麻",
    "薯蓣": "山药",
    "芎藭": "川芎",
    "麦门冬": "麦冬",
    "菝葜": "菝葜",
}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr"):
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.text_parts.append(data)

    def get_text(self):
        return "".join(self.text_parts)


def extract_all_text(epub_path: str) -> str:
    with zipfile.ZipFile(epub_path, "r") as z:
        html_files = sorted(
            [n for n in z.namelist() if n.endswith((".html", ".xhtml", ".htm"))]
        )
        all_text = []
        for fname in html_files:
            content = z.read(fname).decode("utf-8", errors="replace")
            parser = TextExtractor()
            parser.feed(content)
            all_text.append(parser.get_text())
    return "\n".join(all_text)


SECTION_NAMES = ["释名", "集解", "辨疑", "正误", "修治", "气味", "主治", "发明", "附方", "附录"]
SECTION_CHECK = re.compile(r"【(?:" + "|".join(SECTION_NAMES) + r")】")


def find_herb_entries(text: str) -> list[dict]:
    """提取所有药材条目"""
    # 匹配标题：药名 + 可选朝代 + 《来源》
    # 关键：药名和《》之间不能有换行（否则会误匹配章节标题）
    title_pattern = re.compile(
        r"\n"
        r"([\u4e00-\u9fff、]{1,12})"              # 药名（含'、'分隔的双名如'枸杞、地骨皮'）
        r"[^\S\n]{0,2}"                            # 可选空格（不含换行！）
        r"(?:[\u4e00-\u9fff]{0,3}[^\S\n]{0,2})?"   # 可选朝代（宋/唐等1-3字）
        r"[《〈]([^》〉]{1,30})[》〉]"             # 《来源》
    )

    all_titles = list(title_pattern.finditer(text))

    # 过滤：后300字内有【释名】或【集解】等节标题
    valid_titles = []
    for m in all_titles:
        after = text[m.end():m.end() + 300]
        if SECTION_CHECK.search(after):
            valid_titles.append(m)

    print(f"匹配到 {len(valid_titles)} 个有效药材条目")

    entries = []
    for idx, match in enumerate(valid_titles):
        herb_name = match.group(1).strip()
        herb_source = match.group(2).strip()

        # 处理多药名（如"枸杞、地骨皮"）
        if "、" in herb_name:
            herb_name = herb_name.split("、")[0]

        # 清理药名末尾的朝代名（如"何首乌宋" → "何首乌"）
        for dynasty in ["宋", "唐", "明", "元", "清"]:
            if herb_name.endswith(dynasty) and len(herb_name) > 2:
                herb_name = herb_name[:-len(dynasty)]
                break

        # 条目内容范围
        content_start = match.start()
        if idx + 1 < len(valid_titles):
            content_end = valid_titles[idx + 1].start()
        else:
            content_end = min(match.start() + 20000, len(text))

        full_text = text[content_start:content_end].strip()

        # 提取所在卷次
        volume = find_volume(text, match.start())

        # 提取各节内容
        sections = extract_sections(full_text)
        if not sections:
            continue

        # 古今名转换
        modern_name = HERB_NAME_ALIASES.get(herb_name, herb_name)

        entries.append({
            "name": modern_name,
            "original_name": herb_name if herb_name != modern_name else "",
            "original_source": herb_source,
            "volume": volume,
            "sections": sections,
            "full_text": full_text[:5000],
        })

    return entries


def find_volume(text: str, pos: int) -> str:
    search_text = text[max(0, pos - 8000):pos]
    vol_pattern = re.compile(r"第[一二三四五六七八九十百零\d]+卷\s*[　\s]*[\u4e00-\u9fff]+部")
    matches = list(vol_pattern.finditer(search_text))
    if matches:
        return matches[-1].group().strip()
    return ""


def extract_sections(text: str) -> dict:
    sections = {}
    pattern = re.compile(
        r"【(" + "|".join(SECTION_NAMES) + r")】\s*"
        r"([\s\S]*?)"
        r"(?=【(?:" + "|".join(SECTION_NAMES) + r")】|\Z)"
    )
    for match in pattern.finditer(text):
        sec_name = match.group(1)
        sec_content = match.group(2).strip()
        sec_content = re.sub(r"[ \t]+", " ", sec_content)
        sec_content = re.sub(r"\n{3,}", "\n\n", sec_content)
        if sec_content and len(sec_content) > 3:
            sections[sec_name] = sec_content[:3000]
    return sections


def main():
    project_root = Path(__file__).parent.parent.parent
    epub_path = project_root / "本草纲目全本插图版_全五册_赵尚华_赵怀舟_等点校_中华书局_2021.epub"
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)

    fulltext_path = output_dir / "bencao_fulltext.txt"
    if fulltext_path.exists():
        print("使用已缓存的全文...")
        with open(fulltext_path, "r", encoding="utf-8") as f:
            full_text = f.read()
    else:
        print("正在提取epub全文...")
        full_text = extract_all_text(str(epub_path))
        with open(fulltext_path, "w", encoding="utf-8") as f:
            f.write(full_text)

    print(f"全文总字符数：{len(full_text):,}")

    # 提取药材条目
    entries = find_herb_entries(full_text)
    print(f"有效条目：{len(entries)}")

    # 去重（同名条目取内容最长的）
    seen = {}
    for e in entries:
        key = e["name"]
        if key not in seen or len(e["full_text"]) > len(seen[key]["full_text"]):
            seen[key] = e
    unique_entries = list(seen.values())
    print(f"去重后：{len(unique_entries)} 个独立药材")

    # 统计
    vol_stats = {}
    for e in unique_entries:
        vol = e["volume"] or "未知卷"
        vol_stats[vol] = vol_stats.get(vol, 0) + 1

    print("\n=== 各部提取数量 ===")
    for vol, count in sorted(vol_stats.items(), key=lambda x: -x[1])[:15]:
        print(f"  {vol}: {count}")

    sec_stats = {}
    for e in unique_entries:
        for sec in e["sections"]:
            sec_stats[sec] = sec_stats.get(sec, 0) + 1
    print("\n=== 各节覆盖率 ===")
    for sec, count in sorted(sec_stats.items(), key=lambda x: -x[1]):
        pct = count / len(unique_entries) * 100
        print(f"  【{sec}】: {count} ({pct:.0f}%)")

    # 检查关键药材
    key_herbs = [
        "人参", "黄芪", "当归", "地黄", "杜仲", "天麻", "丹参",
        "何首乌", "山药", "茯苓", "甘草", "麦冬", "枸杞",
    ]
    print("\n=== 关键药材检查 ===")
    for h in key_herbs:
        found = [e for e in unique_entries if e["name"] == h]
        if found:
            secs = list(found[0]["sections"].keys())
            print(f"  OK {h} ({found[0]['volume']}) 节: {secs}")
        else:
            print(f"  XX {h}")

    # 保存（含全部条目和去重版本）
    parsed_path = output_dir / "bencao_parsed.json"
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_raw": len(entries),
                "total_unique": len(unique_entries),
                "entries": unique_entries,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\n数据已保存至 {parsed_path}")
    print(f"文件大小：{parsed_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
