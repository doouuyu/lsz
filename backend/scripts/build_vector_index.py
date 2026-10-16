"""构建ChromaDB向量索引

将knowledge_base.json中的所有条目向量化并存入ChromaDB。
使用 text2vec-base-chinese 做中文语义embedding。

用法：
  python3 backend/scripts/build_vector_index.py           # 全量构建
  python3 backend/scripts/build_vector_index.py --rebuild  # 删除旧索引重建
"""

import json
import sys
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
KB_FILE = DATA_DIR / "knowledge_base.json"
CHROMA_DIR = DATA_DIR / "chroma"

EMBEDDING_MODEL = "shibing624/text2vec-base-chinese"
COLLECTION_NAME = "knowledge_base"
BATCH_SIZE = 100


def entry_to_document(entry: dict) -> str:
    """将知识条目转为可embedding的文本。"""
    parts = [
        entry.get("title", ""),
        entry.get("category", ""),
        entry.get("original_text", ""),
        entry.get("plain_explanation", ""),
        entry.get("diagnosis_points", ""),
        entry.get("treatment_method", ""),
        entry.get("modern_mapping", ""),
    ]
    diseases = entry.get("related_diseases", [])
    if diseases:
        parts.append(" ".join(diseases))
    syndromes = entry.get("related_syndromes", [])
    if syndromes:
        parts.append(" ".join(syndromes))
    tags = entry.get("tags", [])
    if tags:
        parts.append(" ".join(tags))

    formula = entry.get("formula")
    if formula and isinstance(formula, dict):
        fname = formula.get("name", "")
        if fname:
            parts.append(fname)
        comp = formula.get("composition", [])
        if isinstance(comp, list):
            herbs = [c.get("herb", "") for c in comp if isinstance(c, dict)]
            parts.append(" ".join(h for h in herbs if h))

    return " ".join(p for p in parts if p)


def entry_metadata(entry: dict) -> dict:
    """提取元数据用于Chroma过滤。"""
    diseases = entry.get("related_diseases", [])
    return {
        "id": entry.get("id", ""),
        "category": entry.get("category", ""),
        "primary_disease": diseases[0] if diseases else "",
        "confidence": float(entry.get("confidence", 0.5)),
        "title": entry.get("title", "")[:200],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="删除旧索引重建")
    args = parser.parse_args()

    print("加载知识库...")
    if not KB_FILE.exists():
        print(f"错误：知识库文件不存在: {KB_FILE}")
        sys.exit(1)

    with open(KB_FILE, "r", encoding="utf-8") as f:
        kb = json.load(f)
    print(f"知识库: {len(kb)} 条")

    print(f"\n加载embedding模型: {EMBEDDING_MODEL}")
    print("（首次运行需下载模型，约400MB）")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("模型加载完成")

    import chromadb
    from chromadb.config import Settings

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    if args.rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
            print("已删除旧索引")
        except Exception:
            pass

    try:
        collection = client.get_collection(COLLECTION_NAME)
        existing = collection.count()
        if existing >= len(kb):
            print(f"向量库已有 {existing} 条，无需重建。若需强制重建请加 --rebuild")
            return
        print(f"向量库已有 {existing} 条，增量添加...")
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print(f"\n开始向量化 {len(kb)} 条...")
    start = time.time()

    documents = [entry_to_document(e) for e in kb]
    ids = [e.get("id", f"entry-{i}") for i, e in enumerate(kb)]
    metadatas = [entry_metadata(e) for e in kb]

    # 分批embedding + 写入
    for batch_start in range(0, len(kb), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(kb))
        batch_docs = documents[batch_start:batch_end]
        batch_ids = ids[batch_start:batch_end]
        batch_meta = metadatas[batch_start:batch_end]

        embeddings = model.encode(batch_docs, show_progress_bar=False).tolist()

        collection.add(
            ids=batch_ids,
            embeddings=embeddings,
            documents=batch_docs,
            metadatas=batch_meta,
        )
        print(f"  {batch_end}/{len(kb)} ({batch_end/len(kb)*100:.0f}%)")

    elapsed = time.time() - start
    print(f"\n构建完成！")
    print(f"  条目数: {collection.count()}")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  存储: {CHROMA_DIR}")

    # 验证：测试查询
    print("\n=== 验证测试 ===")
    test_queries = [
        "头晕目眩 高血压",
        "糖尿病 口渴多饮",
        "关节疼痛 风湿",
        "失眠多梦",
    ]
    for q in test_queries:
        emb = model.encode([q]).tolist()
        results = collection.query(query_embeddings=emb, n_results=3)
        print(f"\n  查询: {q}")
        for rid, dist in zip(results["ids"][0], results["distances"][0]):
            meta = next((m for m in results["metadatas"][0] if True), {})
            idx = results["ids"][0].index(rid)
            meta = results["metadatas"][0][idx]
            print(f"    [{meta.get('category','')}] {meta.get('title','')} (dist={dist:.3f})")


if __name__ == "__main__":
    main()
