"""
知识库补量脚本

策略：
  1. 自动计算各病证×类别缺口
  2. 扩大药材参考范围（每病证20+味），增加多样性
  3. 按辨证维度（证型/体质/兼证）分角度生成，避免重复
  4. 严格去重：prompt注入已有标题 + 生成后过滤
  5. 温度0.5提高多样性

用法：
  python3 backend/scripts/supplement_kb.py
  python3 backend/scripts/supplement_kb.py --dry-run
"""

import json
import re
import sys
import time
from pathlib import Path
from openai import OpenAI

OUTPUT_DIR = Path(__file__).parent.parent / "data"
PARSED_FILE = OUTPUT_DIR / "bencao_parsed.json"
KB_FILE = OUTPUT_DIR / "knowledge_base.json"

API_KEY = ""
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"
MAX_RETRIES = 3
BATCH_SIZE = 10

QUOTA_TABLE = [
    ("中风", "脑血管病", 15, 25, 45, 50, 25),
    ("消渴", "糖尿病", 15, 25, 45, 50, 30),
    ("痹证", "关节炎/骨病", 15, 25, 45, 50, 25),
    ("眩晕", "高血压", 12, 20, 40, 45, 25),
    ("胸痹", "冠心病", 12, 20, 40, 45, 25),
    ("不寐", "失眠", 10, 15, 30, 35, 25),
    ("便秘", "便秘", 8, 12, 25, 30, 20),
    ("咳喘", "慢阻肺", 10, 15, 30, 35, 20),
    ("健忘", "痴呆/认知障碍", 10, 15, 25, 30, 25),
    ("水肿", "慢性肾病", 8, 12, 25, 30, 15),
    ("泄泻", "脾胃虚弱", 8, 12, 25, 30, 20),
    ("虚劳", "衰弱综合征", 12, 18, 30, 35, 30),
    ("郁证", "情志/抑郁", 8, 12, 20, 25, 20),
    ("淋证", "前列腺/泌尿", 6, 10, 20, 25, 10),
    ("耳鸣", "耳鸣耳聋", 5, 8, 15, 20, 15),
    ("通用", "跨病证养生总论", 38, 56, 90, 65, 50),
]
CATEGORIES = ["理", "法", "方", "药", "养生"]

# 扩展药材列表：每病证20+味，包含不常用药材增加多样性
DISEASE_HERBS_EXTENDED = {
    "中风": ["天麻", "钩藤", "川芎", "丹参", "石菖蒲", "地龙", "牛膝", "当归", "红花", "黄芪",
             "全蝎", "僵蚕", "蜈蚣", "水蛭", "白花蛇", "羚羊角", "龟甲", "鳖甲", "桑枝", "鸡血藤",
             "葛根", "菊花", "白芍", "龙骨", "牡蛎", "珍珠母", "代赭石", "决明子"],
    "消渴": ["地黄", "山药", "黄芪", "枸杞", "知母", "天花粉", "麦冬", "玄参", "苍术", "葛根",
             "黄连", "石膏", "竹叶", "生地", "芦根", "石斛", "沙参", "五味子", "桑白皮", "桑叶",
             "乌梅", "人参", "白术", "茯苓", "泽泻", "山茱萸", "牡丹皮", "肉桂"],
    "痹证": ["独活", "桑寄生", "防风", "秦艽", "威灵仙", "杜仲", "牛膝", "细辛", "桂枝", "附子",
             "羌活", "苍术", "薏苡仁", "木瓜", "防己", "络石藤", "海风藤", "豨莶草", "五加皮", "骨碎补",
             "续断", "狗脊", "鹿角胶", "虎杖", "乳香", "没药", "白芥子", "穿山龙"],
    "眩晕": ["天麻", "钩藤", "石决明", "菊花", "枸杞", "地黄", "白芍", "牛膝", "杜仲", "夏枯草",
             "龙骨", "牡蛎", "珍珠母", "代赭石", "磁石", "决明子", "桑寄生", "女贞子", "旱莲草", "山茱萸",
             "黄芩", "栀子", "丹参", "川芎", "葛根", "半夏", "白术", "茯苓"],
    "胸痹": ["丹参", "川芎", "红花", "桃仁", "薤白", "瓜蒌", "三七", "当归", "人参", "黄芪",
             "桂枝", "附子", "细辛", "延胡索", "郁金", "降香", "檀香", "沉香", "石菖蒲", "冰片",
             "枳壳", "陈皮", "半夏", "茯苓", "甘草", "龙骨", "牡蛎", "山楂"],
    "不寐": ["酸枣仁", "远志", "茯苓", "柏子仁", "合欢皮", "夜交藤", "龙眼肉", "甘草", "当归", "地黄",
             "百合", "知母", "黄连", "阿胶", "珍珠母", "龙骨", "牡蛎", "磁石", "琥珀", "朱砂",
             "莲子", "麦冬", "五味子", "半夏", "竹茹", "栀子", "淡豆豉", "灯心草"],
    "便秘": ["大黄", "芒硝", "火麻仁", "郁李仁", "肉苁蓉", "当归", "生地", "枳实", "厚朴", "杏仁",
             "桃仁", "蜂蜜", "决明子", "莱菔子", "槟榔", "番泻叶", "芦荟", "何首乌", "白术", "黄芪",
             "升麻", "柴胡", "木香", "沉香", "麦冬", "玄参", "知母", "锁阳"],
    "咳喘": ["杏仁", "桔梗", "前胡", "紫苑", "款冬花", "百部", "麻黄", "苏子", "半夏", "陈皮",
             "白果", "桑白皮", "葶苈子", "旋覆花", "射干", "马兜铃", "枇杷叶", "川贝母", "浙贝母", "瓜蒌",
             "竹茹", "胆南星", "白前", "紫苏", "荆芥", "防风", "细辛", "干姜"],
    "健忘": ["远志", "石菖蒲", "人参", "茯苓", "龙眼肉", "酸枣仁", "何首乌", "枸杞", "地黄", "当归",
             "益智仁", "鹿茸", "龟甲", "鳖甲", "核桃仁", "桑椹", "黑芝麻", "天麻", "川芎", "丹参",
             "五味子", "白术", "山药", "百合", "麦冬", "黄精", "肉苁蓉", "菟丝子"],
    "水肿": ["茯苓", "猪苓", "泽泻", "车前子", "薏苡仁", "白术", "桂枝", "黄芪", "附子", "大腹皮",
             "冬瓜皮", "赤小豆", "玉米须", "通草", "滑石", "瞿麦", "萹蓄", "海金沙", "石韦", "益母草",
             "防己", "木通", "地肤子", "葫芦", "陈皮", "生姜皮", "人参", "干姜"],
    "泄泻": ["白术", "茯苓", "山药", "莲子", "薏苡仁", "砂仁", "陈皮", "人参", "黄芪", "干姜",
             "肉豆蔻", "补骨脂", "五味子", "吴茱萸", "诃子", "石榴皮", "赤石脂", "禹余粮", "升麻", "葛根",
             "芡实", "扁豆", "大枣", "甘草", "木香", "苍术", "厚朴", "藿香"],
    "虚劳": ["人参", "黄芪", "当归", "地黄", "枸杞", "鹿茸", "冬虫夏草", "山药", "白术", "大枣",
             "阿胶", "龟甲胶", "鹿角胶", "紫河车", "胎盘", "肉苁蓉", "巴戟天", "淫羊藿", "菟丝子", "杜仲",
             "五味子", "黄精", "石斛", "沙参", "麦冬", "天冬", "女贞子", "旱莲草"],
    "郁证": ["柴胡", "白芍", "当归", "茯苓", "薄荷", "香附", "郁金", "合欢皮", "远志", "甘草",
             "川芎", "佛手", "青皮", "陈皮", "枳壳", "木香", "沉香", "玫瑰花", "绿萼梅", "月季花",
             "百合", "知母", "栀子", "丹皮", "石菖蒲", "龙骨", "牡蛎", "琥珀"],
    "淋证": ["车前子", "木通", "滑石", "萹蓄", "瞿麦", "栀子", "甘草", "大黄", "茯苓", "泽泻",
             "海金沙", "金钱草", "石韦", "鸡内金", "琥珀", "冬葵子", "灯心草", "淡竹叶", "白茅根", "小蓟",
             "萆薢", "乌药", "益智仁", "桑螵蛸", "地黄", "知母", "黄柏", "牛膝"],
    "耳鸣": ["磁石", "熟地", "山茱萸", "枸杞", "菖蒲", "远志", "骨碎补", "牛膝", "柴胡", "当归",
             "龙骨", "牡蛎", "珍珠母", "龟甲", "鳖甲", "天麻", "钩藤", "菊花", "蔓荆子", "川芎",
             "黄芪", "人参", "白术", "升麻", "葛根", "蝉蜕", "僵蚕", "地龙"],
    "通用": ["人参", "黄芪", "甘草", "当归", "地黄", "白术", "茯苓", "枸杞", "山药", "大枣",
             "陈皮", "半夏", "生姜", "肉桂", "附子", "川芎", "丹参", "麦冬", "天麻", "杜仲",
             "何首乌", "菊花", "决明子", "桑椹", "黑芝麻", "核桃仁", "莲子", "百合",
             "龙眼肉", "红枣", "蜂蜜", "阿胶", "鹿茸", "黄精", "石斛", "灵芝"],
}

# 生成角度提示：按类别提供不同维度，避免千篇一律
ANGLE_HINTS = {
    "理": [
        "从脏腑辨证角度分析",
        "从气血津液角度分析",
        "从六经辨证角度分析",
        "从体质学说角度分析",
        "从病因病机角度分析",
        "从整体观与天人相应角度分析",
    ],
    "法": [
        "扶正祛邪类治法",
        "调和阴阳类治法",
        "标本缓急类治法",
        "内治外治结合类治法",
        "食疗药治结合类治法",
        "因时因地因人制宜",
    ],
    "方": [
        "经典古方（汉唐宋元名方）",
        "《本草纲目》附方",
        "药对配伍方",
        "食疗验方",
        "外用洗敷方",
        "丸散膏丹剂型方",
    ],
    "药": [
        "草部药材",
        "木部果部药材",
        "金石水土部药材",
        "虫兽禽鱼部药材",
        "药对配伍分析",
        "炮制与用法特殊的药材",
    ],
    "养生": [
        "四时养生（春生夏长秋收冬藏）",
        "饮食养生（药膳食疗粥品茶饮）",
        "起居养生（作息导引功法）",
        "情志养生（调畅情志）",
        "体质调养（九种体质调护）",
        "老年防衰（抗衰延年）",
    ],
}

ENTRY_SCHEMA = """{
  "id": "LSZ-{类别}-{序号}",
  "category": "理/法/方/药/养生",
  "subcategory": "细分类型",
  "title": "条目标题（须唯一，不可与已有标题重复）",
  "source": {"book": "《本草纲目》", "volume": "卷次", "section": "纲目"},
  "original_text": "原文摘录",
  "plain_explanation": "白话释义（至少30字）",
  "related_diseases": ["病证1"],
  "related_syndromes": ["证型"],
  "related_constitution": ["体质"],
  "diagnosis_points": "辨证要点",
  "treatment_method": "治法",
  "formula": {"name": "方名", "composition": [{"herb": "药名", "dosage": "剂量", "role": "君/臣/佐/使"}]},
  "contraindication": "禁忌",
  "modern_mapping": "现代疾病映射",
  "tags": ["标签"],
  "verified": false,
  "confidence": 0.0-1.0
}"""


def load_env():
    global API_KEY, BASE_URL, MODEL
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k == "DEEPSEEK_API_KEY":
                API_KEY = v
            elif k == "DEEPSEEK_BASE_URL":
                BASE_URL = v
            elif k == "DEEPSEEK_MODEL":
                MODEL = v
    if not API_KEY:
        print("错误：请在 backend/.env 中设置 DEEPSEEK_API_KEY")
        sys.exit(1)


def load_bencao_data() -> dict:
    with open(PARSED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def find_relevant_herbs(bencao_data: dict, keywords: list[str], offset: int = 0) -> str:
    """从本草纲目中提取药材原文，offset用于在不同batch取不同药材"""
    entries = bencao_data["entries"]
    relevant = []
    # 根据offset轮转药材列表，每次取不同的药材子集
    rotated = keywords[offset:] + keywords[:offset]
    for kw in rotated:
        for entry in entries:
            if entry["name"] == kw or kw in entry["name"]:
                ft = entry.get("full_text", "")
                text_parts = [f"【{entry['name']}】({entry.get('volume', '')})"]
                for marker in ["【气味】", "【主治】", "【发明】"]:
                    idx = ft.find(marker)
                    if idx >= 0:
                        end = idx + len(marker)
                        next_m = ft.find("【", end)
                        if next_m < 0:
                            next_m = len(ft)
                        seg = ft[end:next_m].strip()[:300]
                        if seg:
                            text_parts.append(f"  [{marker[1:-1]}] {seg}")
                if len(text_parts) > 1:
                    relevant.append("\n".join(text_parts))
                else:
                    sections = entry.get("sections", {})
                    for sec in ["气味", "主治", "发明"]:
                        if sec in sections:
                            text_parts.append(f"  [{sec}] {sections[sec][:300]}")
                    relevant.append("\n".join(text_parts))
                break
    return "\n\n".join(relevant[:10])


def calc_deficits(kb: list[dict]) -> list[dict]:
    """计算各病证×类别的缺口"""
    from collections import Counter

    actual = Counter()
    for e in kb:
        cat = e.get("category", "")
        diseases = e.get("related_diseases", [])
        primary = diseases[0] if diseases else "通用"
        actual[f"{primary}-{cat}"] += 1

    deficits = []
    for disease, modern, li, fa, fang, yao, ys in QUOTA_TABLE:
        quotas = {"理": li, "法": fa, "方": fang, "药": yao, "养生": ys}
        for cat in CATEGORIES:
            target = quotas[cat]
            got = actual.get(f"{disease}-{cat}", 0)
            diff = target - got
            if diff > 0:
                deficits.append({
                    "disease": disease,
                    "modern": next(m for d, m, *_ in QUOTA_TABLE if d == disease),
                    "category": cat,
                    "deficit": diff,
                    "current": got,
                    "target": target,
                })
    return deficits


def generate_supplement_batch(
    client: OpenAI,
    disease: str,
    modern_name: str,
    category: str,
    count: int,
    reference_text: str,
    existing_titles: list[str],
    angle: str,
    batch_idx: int,
) -> list[dict]:
    """生成补量条目"""
    cat_desc = {
        "理": "学术思想、病机理论、整体观念",
        "法": "治法、辨证方法、治疗原则",
        "方": "方剂、经典名方、临床常用方",
        "药": "单味药材、药性分析、功效记载",
        "养生": "四时养生、食疗药膳、起居功法",
    }
    id_letter = {"理": "LI", "法": "FA", "方": "FANG", "药": "YAO", "养生": "YS"}

    titles_str = ""
    if existing_titles:
        titles_str = f"\n\n【已有条目标题，严禁重复】\n{chr(10).join('- ' + t for t in existing_titles[-60:])}\n"

    prompt = f"""你是中医文献整理专家，精通李时珍《本草纲目》及其老年病学术思想。

请围绕【{disease}（现代对应：{modern_name}）】，从「{angle}」的角度，生成 {count} 条「{category}」类（{cat_desc[category]}）结构化知识条目。

以下是《本草纲目》中相关药材的真实记载，供参考和引用：
---
{reference_text}
---
{titles_str}
要求：
1. category 固定为「{category}」。
2. id 格式为 "LSZ-{id_letter[category]}-S{batch_idx:02d}{'{:02d}'.format(0)}" 起递增（S表示补充条目）。
3. original_text 仅摘录你确信真实存在的本草纲目记载，优先从上方原文中引用。
4. plain_explanation 白话释义至少30字，需有实质内容。
5. formula 仅在「方」类条目中填写。
6. confidence 如实评估。
7. modern_mapping 映射到「{modern_name}」及相关老年慢病。
8. 每条标题必须唯一，侧重不同，严禁与已有标题重复或用近义词变体重复。
9. 从「{angle}」角度切入，体现多样性和专业深度。

严格输出合法 JSON 数组。每个元素结构：
{ENTRY_SCHEMA}"""

    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "你是中医文献整理专家。严格按要求输出JSON数组，不附加任何其他文字。每条标题必须独特，不得重复。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=4096 * 2,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content.strip()
            data = json.loads(content)

            if isinstance(data, dict):
                for key in ["entries", "data", "items", "knowledge_entries", "条目"]:
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
                else:
                    if isinstance(data, dict):
                        data = [data]

            if not isinstance(data, list):
                raise ValueError(f"返回格式不是数组: {type(data)}")

            return data

        except json.JSONDecodeError as e:
            print(f"    JSON解析失败(尝试{attempt+1}): {e}")
            match = re.search(r"\[[\s\S]*\]", content)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

        except Exception as e:
            print(f"    API失败(尝试{attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

    return []


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env()

    print("加载数据...")
    bencao_data = load_bencao_data()
    kb = json.load(open(KB_FILE, "r", encoding="utf-8"))
    print(f"当前知识库: {len(kb)} 条")

    deficits = calc_deficits(kb)
    total_deficit = sum(d["deficit"] for d in deficits)
    print(f"总缺口: {total_deficit} 条, 涉及 {len(deficits)} 个病证×类别组合")

    if args.dry_run:
        print("\n=== 补量计划 ===")
        for d in sorted(deficits, key=lambda x: -x["deficit"]):
            print(f"  {d['disease']}-{d['category']}: 缺 {d['deficit']} ({d['current']}/{d['target']})")
        return

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    existing_titles = set(e.get("title", "") for e in kb)
    generated = 0
    deduped = 0
    failed = 0
    batch_global = 0
    start_time = time.time()

    for di, deficit in enumerate(deficits):
        disease = deficit["disease"]
        cat = deficit["category"]
        need = deficit["deficit"]
        modern = deficit["modern"]

        keywords = DISEASE_HERBS_EXTENDED.get(disease, DISEASE_HERBS_EXTENDED["通用"])
        angles = ANGLE_HINTS.get(cat, ["综合角度"])

        # 按角度分批生成
        remaining = need
        angle_idx = 0
        while remaining > 0:
            batch_count = min(BATCH_SIZE, remaining)
            angle = angles[angle_idx % len(angles)]
            herb_offset = (angle_idx * 5) % len(keywords)

            reference_text = find_relevant_herbs(bencao_data, keywords, offset=herb_offset)

            # 收集当前病证+类别的已有标题
            disease_titles = [t for t in existing_titles
                              if any(e.get("title") == t and disease in e.get("related_diseases", [])
                                     and e.get("category") == cat for e in kb)]
            # 简化：直接收集所有已有标题中与disease相关的
            disease_titles = list(existing_titles)

            batch_global += 1
            print(f"\n[{di+1}/{len(deficits)}] {disease}-{cat} 补{batch_count}条 (角度:{angle[:10]}...) [{generated}/{total_deficit}]")

            batch = generate_supplement_batch(
                client, disease, modern, cat, batch_count,
                reference_text, disease_titles, angle, batch_global,
            )

            if batch:
                new_batch = []
                for entry in batch:
                    title = entry.get("title", "")
                    if title and title not in existing_titles:
                        new_batch.append(entry)
                        existing_titles.add(title)
                    else:
                        deduped += 1
                kb.extend(new_batch)
                generated += len(new_batch)
                skipped = len(batch) - len(new_batch)
                msg = f"    +{len(new_batch)} 条"
                if skipped:
                    msg += f" (去重{skipped})"
                print(f"{msg} (累计 {len(kb)})")
            else:
                failed += batch_count
                print(f"    失败！跳过 {batch_count}")

            remaining -= batch_count
            angle_idx += 1

            # 保存
            with open(KB_FILE, "w", encoding="utf-8") as f:
                json.dump(kb, f, ensure_ascii=False, indent=2)

            time.sleep(0.5)

    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"补量完成！")
    print(f"  新增: {generated} 条")
    print(f"  去重: {deduped} 条")
    print(f"  失败: {failed} 条")
    print(f"  总计: {len(kb)} 条")
    print(f"  耗时: {elapsed/60:.1f} 分钟")

    from collections import Counter
    cat_stats = Counter(e["category"] for e in kb)
    print(f"\n类别分布:")
    for c in CATEGORIES:
        print(f"  {c}: {cat_stats.get(c, 0)}")


if __name__ == "__main__":
    main()
