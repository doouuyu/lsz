"""
知识库2000条批量生成脚本

策略：
  1. 按「病证 × 类别(理/法/方/药/养生)」配额表分批生成
  2. 每批注入本草纲目真实原文作为参考
  3. DeepSeek API 调用 + JSON 解析 + 自动重试
  4. 增量保存，可中断恢复

用法：
  python3 backend/scripts/generate_kb.py              # 生成全部
  python3 backend/scripts/generate_kb.py --resume      # 从上次中断处继续
  python3 backend/scripts/generate_kb.py --disease 消渴  # 只生成某个病证
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from openai import OpenAI

# ===== 配置 =====
API_KEY = ""
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"
BATCH_SIZE = 10         # 每次API调用生成的条目数
MAX_RETRIES = 3
OUTPUT_DIR = Path(__file__).parent.parent / "data"
PARSED_FILE = OUTPUT_DIR / "bencao_parsed.json"
KB_FILE = OUTPUT_DIR / "knowledge_base.json"
PROGRESS_FILE = OUTPUT_DIR / "kb_progress.json"

# ===== 配额表（来自开发文档B2） =====
QUOTA_TABLE = [
    # (病证, 现代对应, 理, 法, 方, 药, 养生)
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

# ===== 病证关键词→本草纲目药材映射 =====
DISEASE_HERB_KEYWORDS = {
    "中风": ["天麻", "钩藤", "川芎", "丹参", "石菖蒲", "地龙", "牛膝", "当归", "红花", "黄芪"],
    "消渴": ["地黄", "山药", "黄芪", "枸杞", "知母", "天花粉", "麦冬", "玄参", "苍术", "葛根"],
    "痹证": ["独活", "桑寄生", "防风", "秦艽", "威灵仙", "杜仲", "牛膝", "细辛", "桂枝", "附子"],
    "眩晕": ["天麻", "钩藤", "石决明", "菊花", "枸杞", "地黄", "白芍", "牛膝", "杜仲", "夏枯草"],
    "胸痹": ["丹参", "川芎", "红花", "桃仁", "薤白", "瓜蒌", "三七", "当归", "人参", "黄芪"],
    "不寐": ["酸枣仁", "远志", "茯苓", "柏子仁", "合欢皮", "夜交藤", "龙眼肉", "甘草", "当归", "地黄"],
    "便秘": ["大黄", "芒硝", "火麻仁", "郁李仁", "肉苁蓉", "当归", "生地", "枳实", "厚朴", "杏仁"],
    "咳喘": ["杏仁", "桔梗", "前胡", "紫苑", "款冬花", "百部", "麻黄", "苏子", "半夏", "陈皮"],
    "健忘": ["远志", "石菖蒲", "人参", "茯苓", "龙眼肉", "酸枣仁", "何首乌", "枸杞", "地黄", "当归"],
    "水肿": ["茯苓", "猪苓", "泽泻", "车前子", "薏苡仁", "白术", "桂枝", "黄芪", "附子", "大腹皮"],
    "泄泻": ["白术", "茯苓", "山药", "莲子", "薏苡仁", "砂仁", "陈皮", "人参", "黄芪", "干姜"],
    "虚劳": ["人参", "黄芪", "当归", "地黄", "枸杞", "鹿茸", "冬虫夏草", "山药", "白术", "大枣"],
    "郁证": ["柴胡", "白芍", "当归", "茯苓", "薄荷", "香附", "郁金", "合欢皮", "远志", "甘草"],
    "淋证": ["车前子", "木通", "滑石", "萹蓄", "瞿麦", "栀子", "甘草", "大黄", "茯苓", "泽泻"],
    "耳鸣": ["磁石", "熟地", "山茱萸", "枸杞", "菖蒲", "远志", "骨碎补", "牛膝", "柴胡", "当归"],
    "通用": ["人参", "黄芪", "甘草", "当归", "地黄", "白术", "茯苓", "枸杞", "山药", "大枣",
            "陈皮", "半夏", "生姜", "肉桂", "附子", "川芎", "丹参", "麦冬", "天麻", "杜仲"],
}

# ===== JSON Schema（简化版，写入prompt） =====
ENTRY_SCHEMA = """{
  "id": "LSZ-{类别首字母}-{四位序号}",
  "category": "理/法/方/药/养生",
  "subcategory": "如：整体观/辨证法/经典方/单味药/四时养生",
  "title": "条目标题",
  "source": {"book": "《本草纲目》", "volume": "如 卷十二·草部", "section": "如 黄芪"},
  "original_text": "原文摘录（仅填确信真实存在的内容，不确定填空）",
  "plain_explanation": "白话释义",
  "related_diseases": ["中风", "消渴"],
  "related_syndromes": ["气虚血瘀", "阴虚火旺"],
  "related_constitution": ["气虚质", "阴虚质"],
  "diagnosis_points": "辨证要点",
  "treatment_method": "治法",
  "formula": {"name": "方名", "composition": [{"herb": "药名", "dosage": "剂量", "role": "君/臣/佐/使"}]},
  "contraindication": "禁忌",
  "modern_mapping": "对应现代疾病",
  "tags": ["标签1", "标签2"],
  "verified": false,
  "confidence": 0.0-1.0
}"""


def load_env():
    """从.env文件加载API Key"""
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
    """加载解析后的本草纲目数据"""
    with open(PARSED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def find_relevant_herbs(bencao_data: dict, keywords: list[str]) -> str:
    """根据关键词从本草纲目中提取相关药材原文"""
    entries = bencao_data["entries"]
    relevant = []
    for kw in keywords:
        for entry in entries:
            if entry["name"] == kw or kw in entry["name"]:
                sections = entry.get("sections", {})
                text_parts = [f"【{entry['name']}】({entry.get('volume', '')})"]
                for sec in ["气味", "主治", "发明"]:
                    if sec in sections:
                        text_parts.append(f"  [{sec}] {sections[sec][:300]}")
                relevant.append("\n".join(text_parts))
                break
    return "\n\n".join(relevant[:8])  # 限制总长度


def generate_batch(
    client: OpenAI,
    disease: str,
    modern_name: str,
    category: str,
    count: int,
    reference_text: str,
    id_prefix: str,
    start_num: int,
    existing_titles: list[str] = None,
) -> list[dict]:
    """调用DeepSeek生成一批知识条目"""

    cat_desc = {
        "理": "学术思想、病机理论、整体观念",
        "法": "治法、辨证方法、治疗原则",
        "方": "方剂、经典名方、临床常用方",
        "药": "单味药材、药性分析、功效记载",
        "养生": "四时养生、食疗药膳、起居功法",
    }

    id_letter = {"理": "LI", "法": "FA", "方": "FANG", "药": "YAO", "养生": "YS"}

    dedup_clause = ""
    if existing_titles:
        titles_str = "、".join(existing_titles[-50:])
        dedup_clause = f"\n9. 以下标题已生成，严禁重复或换近义词重复：{titles_str}\n"

    prompt = f"""你是中医文献整理专家，精通李时珍《本草纲目》及其老年病学术思想。

请围绕【{disease}（现代对应：{modern_name}）】，生成 {count} 条「{category}」类（{cat_desc[category]}）结构化知识条目。

以下是《本草纲目》中与该病证相关的真实药材记载，供你参考和引用：
---
{reference_text}
---

要求：
1. category 固定为「{category}」。
2. id 格式为 "{id_prefix}-{id_letter[category]}-{start_num:04d}" 起递增。
3. source 字段填写真实《本草纲目》卷次；无法确定的 volume 填"待校"。
4. original_text 仅摘录你确信真实存在的本草纲目记载，优先从上方原文中引用；不确定的内容放 plain_explanation。
5. formula 仅在「方」类条目中填写，且配伍须符合中医方剂学常识。
6. confidence 如实评估：有确切出处的 0.7-0.9，出处不确定的 0.3-0.5。
7. modern_mapping 映射到「{modern_name}」及相关现代老年慢病。
8. 每条须有不同侧重，避免重复。{dedup_clause}

严格输出合法 JSON 数组，不要附加任何其他文字。每个元素结构：
{ENTRY_SCHEMA}"""

    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "你是中医文献整理专家。严格按要求输出JSON数组，不附加任何其他文字。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4096 * 2,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content.strip()

            # 解析JSON
            data = json.loads(content)

            # 处理不同返回格式（有时包在一个对象里）
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
            print(f"    JSON解析失败(尝试{attempt+1}/{MAX_RETRIES}): {e}")
            # 尝试提取JSON数组
            match = re.search(r"\[[\s\S]*\]", content)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

        except Exception as e:
            print(f"    API调用失败(尝试{attempt+1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

    return []


def load_progress() -> dict:
    """加载生成进度"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"completed": [], "total_generated": 0}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def load_existing_kb() -> list[dict]:
    if KB_FILE.exists():
        with open(KB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_kb(entries: list[dict]):
    with open(KB_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="生成李时珍知识库条目")
    parser.add_argument("--resume", action="store_true", help="从上次中断处继续")
    parser.add_argument("--disease", type=str, help="只生成指定病证")
    parser.add_argument("--dry-run", action="store_true", help="只显示计划，不实际生成")
    args = parser.parse_args()

    load_env()
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("加载本草纲目数据...")
    bencao_data = load_bencao_data()
    print(f"已加载 {bencao_data['total_unique']} 个药材条目")

    # 初始化客户端
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    # 加载进度
    progress = load_progress() if args.resume else {"completed": [], "total_generated": 0}
    all_entries = load_existing_kb() if args.resume else []

    # 构建任务列表
    tasks = []
    global_id = progress["total_generated"]
    for disease, modern, li, fa, fang, yao, ys in QUOTA_TABLE:
        if args.disease and disease != args.disease:
            continue
        quotas = {"理": li, "法": fa, "方": fang, "药": yao, "养生": ys}
        for cat, count in quotas.items():
            task_key = f"{disease}-{cat}"
            if task_key in progress["completed"]:
                global_id += count
                continue
            # 分批（每批BATCH_SIZE条）
            remaining = count
            batch_start = global_id
            while remaining > 0:
                batch_count = min(BATCH_SIZE, remaining)
                tasks.append({
                    "disease": disease,
                    "modern": modern,
                    "category": cat,
                    "count": batch_count,
                    "id_prefix": "LSZ",
                    "start_num": batch_start,
                    "task_key": task_key,
                })
                batch_start += batch_count
                remaining -= batch_count
            global_id = batch_start

    # 统计
    total_to_generate = sum(t["count"] for t in tasks)
    print(f"\n计划生成 {total_to_generate} 条（已完成 {progress['total_generated']} 条）")
    print(f"共 {len(tasks)} 个批次，每批 ≤{BATCH_SIZE} 条")

    if args.dry_run:
        print("\n=== 任务计划 ===")
        for t in tasks[:20]:
            print(f"  {t['disease']}-{t['category']}: {t['count']}条 (ID从{t['start_num']})")
        if len(tasks) > 20:
            print(f"  ... 共{len(tasks)}个批次")
        return

    # 逐批生成
    generated_count = 0
    failed_count = 0
    dedup_count = 0
    start_time = time.time()
    existing_titles = set(e.get("title", "") for e in all_entries)

    for i, task in enumerate(tasks):
        disease = task["disease"]
        cat = task["category"]
        count = task["count"]
        keywords = DISEASE_HERB_KEYWORDS.get(disease, DISEASE_HERB_KEYWORDS["通用"])
        reference_text = find_relevant_herbs(bencao_data, keywords)

        # 收集当前病证+类别已有标题用于去重提示
        disease_titles = [e.get("title", "") for e in all_entries
                          if disease in e.get("related_diseases", []) and e.get("category") == cat]

        print(f"\n[{i+1}/{len(tasks)}] {disease}-{cat} 生成{count}条...")

        batch = generate_batch(
            client,
            disease=disease,
            modern_name=task["modern"],
            category=cat,
            count=count,
            reference_text=reference_text,
            id_prefix=task["id_prefix"],
            start_num=task["start_num"],
            existing_titles=disease_titles,
        )

        if batch:
            new_batch = []
            for entry in batch:
                title = entry.get("title", "")
                if title and title not in existing_titles:
                    new_batch.append(entry)
                    existing_titles.add(title)
                else:
                    dedup_count += 1
            all_entries.extend(new_batch)
            generated_count += len(new_batch)
            skipped = len(batch) - len(new_batch)
            msg = f"    成功 {len(new_batch)} 条"
            if skipped:
                msg += f" (去重跳过 {skipped})"
            print(f"{msg} (累计 {len(all_entries)})")
        else:
            failed_count += count
            print(f"    失败！跳过 {count} 条")

        # 每个task_key完成时更新进度
        if task == [t for t in tasks if t["task_key"] == task["task_key"]][-1]:
            progress["completed"].append(task["task_key"])

        progress["total_generated"] = len(all_entries)
        save_progress(progress)
        save_kb(all_entries)

        # 控制速率
        time.sleep(0.5)

    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"生成完成！")
    print(f"  成功: {generated_count} 条")
    print(f"  去重: {dedup_count} 条")
    print(f"  失败: {failed_count} 条")
    print(f"  总计: {len(all_entries)} 条")
    print(f"  耗时: {elapsed/60:.1f} 分钟")
    print(f"  保存: {KB_FILE}")

    # 按类别统计
    cat_stats = {}
    for e in all_entries:
        c = e.get("category", "未知")
        cat_stats[c] = cat_stats.get(c, 0) + 1
    print(f"\n=== 类别分布 ===")
    for c, n in sorted(cat_stats.items()):
        print(f"  {c}: {n}")


if __name__ == "__main__":
    main()
