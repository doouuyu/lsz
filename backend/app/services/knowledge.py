"""知识库服务 - BM25 + ChromaDB向量混合检索

架构：
  - 启动时加载 knowledge_base.json 到内存 + BM25索引
  - ChromaDB 持久化向量库，用 text2vec-base-chinese 做中文 embedding
  - 混合检索：BM25关键词(0.4权重) + 向量语义(0.6权重)
  - 向量库不可用时自动降级为纯BM25
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.knowledge import (
    KnowledgeEntry,
    GraphNode,
    GraphLink,
    KnowledgeGraph,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
KB_FILE = DATA_DIR / "knowledge_base.json"

# 可选依赖：优雅降级
try:
    import jieba  # type: ignore
    jieba.setLogLevel(logging.WARNING)
    _HAS_JIEBA = True
except Exception:
    _HAS_JIEBA = False

try:
    from rank_bm25 import BM25Okapi  # type: ignore
    _HAS_BM25 = True
except Exception:
    _HAS_BM25 = False

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _HAS_CHROMA = True
except Exception:
    _HAS_CHROMA = False

_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Embedding模型已加载: %s", settings.EMBEDDING_MODEL)
        except Exception as e:
            logger.warning("Embedding模型加载失败: %s", e)
    return _embedding_model


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    if _HAS_JIEBA:
        return [t for t in jieba.lcut(text) if t.strip()]
    chars = [c for c in text if c.strip()]
    bigrams = ["".join(pair) for pair in zip(chars, chars[1:])]
    return chars + bigrams


class KnowledgeService:
    """知识库单例服务。"""

    def __init__(self) -> None:
        self.entries: list[KnowledgeEntry] = []
        self._by_id: dict[str, KnowledgeEntry] = {}
        self._corpus_tokens: list[list[str]] = []
        self._bm25 = None
        self._chroma_collection = None
        self._loaded = False

    # ---------- 加载 ----------
    def load(self, path: Optional[Path] = None) -> int:
        path = path or KB_FILE
        if not path.exists():
            logger.warning("知识库文件不存在: %s（服务以空库启动）", path)
            self._loaded = True
            return 0

        raw = json.loads(path.read_text(encoding="utf-8"))
        entries: list[KnowledgeEntry] = []
        for item in raw:
            try:
                entries.append(KnowledgeEntry.model_validate(item))
            except Exception as e:
                logger.debug("跳过非法条目 %s: %s", item.get("id"), e)

        self.entries = entries
        self._by_id = {e.id: e for e in entries}
        self._build_bm25_index()
        self._load_chroma()
        self._loaded = True
        logger.info(
            "知识库已加载：%d 条 | BM25=%s | Chroma=%s",
            len(entries), bool(self._bm25), bool(self._chroma_collection),
        )
        return len(entries)

    def _entry_text(self, e: KnowledgeEntry) -> str:
        parts = [
            e.title,
            e.subcategory,
            e.original_text,
            e.plain_explanation,
            e.diagnosis_points,
            e.treatment_method,
            e.modern_mapping,
            " ".join(e.related_diseases),
            " ".join(e.related_syndromes),
            " ".join(e.related_constitution),
            " ".join(e.tags),
        ]
        if e.formula:
            parts.append(e.formula.name)
            parts.extend(h.herb for h in e.formula.composition)
        return " ".join(p for p in parts if p)

    def _build_bm25_index(self) -> None:
        self._corpus_tokens = [_tokenize(self._entry_text(e)) for e in self.entries]
        if _HAS_BM25 and self._corpus_tokens:
            self._bm25 = BM25Okapi(self._corpus_tokens)

    def _load_chroma(self) -> None:
        if not _HAS_CHROMA:
            logger.info("chromadb未安装，向量检索不可用")
            return

        chroma_dir = DATA_DIR / "chroma"
        if not chroma_dir.exists():
            logger.info("Chroma向量库目录不存在: %s（需要先运行 build_vector_index.py）", chroma_dir)
            return

        try:
            client = chromadb.PersistentClient(
                path=str(chroma_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._chroma_collection = client.get_collection("knowledge_base")
            count = self._chroma_collection.count()
            logger.info("Chroma向量库已加载: %d 条", count)
        except Exception as e:
            logger.warning("Chroma加载失败: %s（降级为纯BM25）", e)
            self._chroma_collection = None

    # ---------- 检索 ----------
    def _ranked_indices(
        self,
        query: str,
        category: Optional[str] = None,
        disease: Optional[str] = None,
        verified_only: bool = False,
        fallback_all: bool = True,
    ) -> list[int]:
        """返回按相关度排序的条目下标（未截断）。

        fallback_all=True：无命中时回退为全部候选（RAG 需要兜底上下文）。
        fallback_all=False：无命中时返回空（检索 UI 应如实显示“无结果”）。
        """
        if not self._loaded:
            self.load()

        candidates = list(range(len(self.entries)))
        if category:
            candidates = [i for i in candidates if self.entries[i].category == category]
        if disease:
            candidates = [
                i for i in candidates if disease in self.entries[i].related_diseases
                or disease in self.entries[i].modern_mapping
            ]
        if verified_only:
            candidates = [i for i in candidates if self.entries[i].verified]

        if not query or not query.strip():
            return candidates

        scores = self._hybrid_score(query, candidates)
        ranked = [i for i, _ in sorted(scores, key=lambda x: x[1], reverse=True) if _ > 0]
        if not ranked and fallback_all:
            ranked = candidates
        return ranked

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        disease: Optional[str] = None,
        verified_only: bool = False,
        top_k: int = 10,
        offset: int = 0,
    ) -> list[KnowledgeEntry]:
        ranked = self._ranked_indices(query, category, disease, verified_only)
        return [self.entries[i] for i in ranked[offset:offset + top_k]]

    def search_page(
        self,
        query: str,
        category: Optional[str] = None,
        disease: Optional[str] = None,
        verified_only: bool = False,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[int, list[KnowledgeEntry]]:
        """检索 UI 专用：返回 (真实命中总数, 当前页条目)。无命中时不兜底。"""
        ranked = self._ranked_indices(
            query, category, disease, verified_only, fallback_all=False
        )
        total = len(ranked)
        start = max(0, (page - 1) * page_size)
        page_idx = ranked[start:start + page_size]
        return total, [self.entries[i] for i in page_idx]

    def search_for_rag(
        self,
        query: str,
        disease: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> list[dict]:
        """RAG专用检索：返回结构化上下文，注入LLM prompt。"""
        k = top_k or settings.RAG_TOP_K
        entries = self.search(query=query, disease=disease, top_k=k)
        contexts = []
        for e in entries:
            ctx = {
                "id": e.id,
                "category": e.category,
                "title": e.title,
                "original_text": e.original_text,
                "plain_explanation": e.plain_explanation,
                "source": f"{e.source.book} {e.source.volume} {e.source.section}".strip(),
            }
            if e.formula and e.formula.name:
                herbs = "、".join(f"{h.herb}({h.role})" for h in e.formula.composition if h.herb)
                ctx["formula"] = f"{e.formula.name}：{herbs}"
            if e.diagnosis_points:
                ctx["diagnosis_points"] = e.diagnosis_points
            if e.treatment_method:
                ctx["treatment_method"] = e.treatment_method
            contexts.append(ctx)
        return contexts

    def format_rag_context(self, contexts: list[dict]) -> str:
        """将检索结果格式化为LLM可读的参考文本。"""
        if not contexts:
            return ""
        lines = ["以下是从《本草纲目》知识库中检索到的相关条目，供辨证参考：", ""]
        for i, ctx in enumerate(contexts, 1):
            lines.append(f"【参考{i}】{ctx['title']}（{ctx['category']}）")
            if ctx.get("original_text"):
                lines.append(f"  原文：{ctx['original_text']}")
            if ctx.get("plain_explanation"):
                lines.append(f"  释义：{ctx['plain_explanation']}")
            if ctx.get("formula"):
                lines.append(f"  方剂：{ctx['formula']}")
            if ctx.get("diagnosis_points"):
                lines.append(f"  辨证：{ctx['diagnosis_points']}")
            if ctx.get("source"):
                lines.append(f"  出处：{ctx['source']}")
            lines.append("")
        return "\n".join(lines)

    def _hybrid_score(self, query: str, candidate_idx: list[int]) -> list[tuple[int, float]]:
        q_tokens = _tokenize(query)

        # BM25 分数
        bm25_scores: dict[int, float] = {}
        if self._bm25 is not None:
            raw = self._bm25.get_scores(q_tokens)
            mx = max(raw) if len(raw) else 0.0
            if mx > 0:
                for i in candidate_idx:
                    bm25_scores[i] = raw[i] / mx

        # 向量检索分数
        vec_scores = self._vector_scores(query, candidate_idx)

        a = settings.RAG_VECTOR_WEIGHT
        b = settings.RAG_BM25_WEIGHT
        out: list[tuple[int, float]] = []
        for i in candidate_idx:
            score = a * vec_scores.get(i, 0.0) + b * bm25_scores.get(i, 0.0)
            out.append((i, score))
        return out

    def _vector_scores(self, query: str, candidate_idx: list[int]) -> dict[int, float]:
        """ChromaDB向量检索（使用与构建索引相同的embedding模型）。不可用时降级为Jaccard。"""
        if self._chroma_collection is None:
            return self._jaccard_scores(_tokenize(query), candidate_idx)

        model = _get_embedding_model()
        if model is None:
            return self._jaccard_scores(_tokenize(query), candidate_idx)

        try:
            query_emb = model.encode([query]).tolist()
            candidate_ids = [self.entries[i].id for i in candidate_idx]
            results = self._chroma_collection.query(
                query_embeddings=query_emb,
                n_results=min(len(candidate_ids), 50),
                where={"id": {"$in": candidate_ids}} if len(candidate_ids) < len(self.entries) else None,
            )

            id_to_idx = {self.entries[i].id: i for i in candidate_idx}
            scores: dict[int, float] = {}
            if results and results["ids"] and results["distances"]:
                ids = results["ids"][0]
                dists = results["distances"][0]
                if dists:
                    max_dist = max(dists) if dists else 1.0
                    for eid, dist in zip(ids, dists):
                        if eid in id_to_idx:
                            scores[id_to_idx[eid]] = 1.0 - (dist / max_dist) if max_dist > 0 else 1.0
            return scores
        except Exception as e:
            logger.warning("Chroma查询失败: %s（降级Jaccard）", e)
            return self._jaccard_scores(_tokenize(query), candidate_idx)

    def _jaccard_scores(self, q_tokens: list[str], candidate_idx: list[int]) -> dict[int, float]:
        q_set = set(q_tokens)
        if not q_set:
            return {}
        out: dict[int, float] = {}
        for i in candidate_idx:
            doc_set = set(self._corpus_tokens[i]) if i < len(self._corpus_tokens) else set()
            if not doc_set:
                continue
            inter = len(q_set & doc_set)
            if inter:
                out[i] = inter / len(q_set | doc_set)
        return out

    # ---------- 单条 ----------
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        if not self._loaded:
            self.load()
        return self._by_id.get(entry_id)

    # ---------- 图谱 ----------
    def build_graph(self, disease: Optional[str] = None, max_entries: int = 200) -> KnowledgeGraph:
        if not self._loaded:
            self.load()

        entries = self.entries
        if disease:
            entries = [
                e for e in entries
                if disease in e.related_diseases or disease in e.modern_mapping
            ]
        entries = entries[:max_entries]

        nodes: dict[str, GraphNode] = {}
        links: list[GraphLink] = []
        seen_links: set[tuple[str, str, str]] = set()

        def add_node(nid: str, ntype: str) -> None:
            if not nid:
                return
            if nid in nodes:
                nodes[nid].weight += 1
            else:
                nodes[nid] = GraphNode(id=nid, type=ntype, label=nid, weight=1)

        def add_link(src: str, tgt: str, rel: str) -> None:
            if not src or not tgt:
                return
            key = (src, tgt, rel)
            if key in seen_links:
                return
            seen_links.add(key)
            links.append(GraphLink(source=src, target=tgt, relation=rel))

        for e in entries:
            diseases = e.related_diseases or []
            for d in diseases:
                add_node(d, "disease")

            if e.treatment_method:
                add_node(e.treatment_method, "treatment")
                for d in diseases:
                    add_link(d, e.treatment_method, "治法")

            if e.formula and e.formula.name:
                add_node(e.formula.name, "formula")
                if e.treatment_method:
                    add_link(e.treatment_method, e.formula.name, "代表方")
                for d in diseases:
                    add_link(d, e.formula.name, "主方")
                for comp in e.formula.composition:
                    if comp.herb:
                        add_node(comp.herb, "herb")
                        add_link(e.formula.name, comp.herb, "组成")

            for syn in e.related_syndromes:
                add_node(syn, "syndrome")
                for d in diseases:
                    add_link(d, syn, "证型")

        return KnowledgeGraph(nodes=list(nodes.values()), links=links)

    # ---------- 统计 ----------
    def stats(self) -> dict:
        from collections import Counter
        cat = Counter(e.category for e in self.entries)
        return {
            "total": len(self.entries),
            "verified": sum(e.verified for e in self.entries),
            "by_category": dict(cat),
            "engine": {
                "jieba": _HAS_JIEBA,
                "bm25": _HAS_BM25,
                "chroma": self._chroma_collection is not None,
            },
        }

    def evaluation(self) -> dict:
        """生成知识库完整评估报告数据（首次计算后缓存）。"""
        if hasattr(self, '_eval_cache') and self._eval_cache:
            return self._eval_cache
        if not self._loaded:
            self.load()
        from collections import Counter

        total = len(self.entries)
        if total == 0:
            return {"total": 0}

        # 分类分布
        cat_dist = Counter(e.category for e in self.entries)

        # 病种覆盖
        disease_counter: Counter = Counter()
        for e in self.entries:
            for d in e.related_diseases:
                disease_counter[d] += 1
        core_diseases = [
            "眩晕", "消渴", "胸痹", "不寐", "痹证", "中风",
            "虚劳", "便秘", "泄泻", "水肿", "郁证", "慢阻肺",
            "健忘", "咳喘", "痴呆", "淋证",
        ]
        core_coverage = {d: disease_counter.get(d, 0) for d in core_diseases}

        # 置信度分布
        confs = [e.confidence for e in self.entries]
        conf_bands = {"0.9-1.0": 0, "0.8-0.9": 0, "0.7-0.8": 0, "0.6-0.7": 0, "<0.6": 0}
        for c in confs:
            if c >= 0.9:
                conf_bands["0.9-1.0"] += 1
            elif c >= 0.8:
                conf_bands["0.8-0.9"] += 1
            elif c >= 0.7:
                conf_bands["0.7-0.8"] += 1
            elif c >= 0.6:
                conf_bands["0.6-0.7"] += 1
            else:
                conf_bands["<0.6"] += 1
        high_conf_rate = sum(1 for c in confs if c >= 0.7) / total

        # 原文溯源率
        has_original = sum(1 for e in self.entries if (e.original_text or "").strip())
        traceability = has_original / total

        # 已验证率
        verified = sum(1 for e in self.entries if e.verified)

        # 方剂覆盖
        has_formula = sum(1 for e in self.entries if e.formula and e.formula.name)

        # 分类×病种交叉覆盖矩阵（核心16病种 × 5分类）
        cross_matrix: dict[str, dict[str, int]] = {}
        for d in core_diseases:
            cross_matrix[d] = {cat: 0 for cat in ["理", "法", "方", "药", "养生"]}
        for e in self.entries:
            for d in e.related_diseases:
                if d in cross_matrix:
                    if e.category in cross_matrix[d]:
                        cross_matrix[d][e.category] += 1

        # 检索准确性抽测
        test_cases = [
            {"query": "头晕目眩，血压偏高", "expect_disease": "眩晕"},
            {"query": "口渴多饮，消瘦乏力", "expect_disease": "消渴"},
            {"query": "膝关节肿痛，阴雨天加重", "expect_disease": "痹证"},
            {"query": "夜不能寐，心烦多梦", "expect_disease": "不寐"},
            {"query": "胸闷气短，心前区疼痛", "expect_disease": "胸痹"},
            {"query": "半身不遂，口眼歪斜", "expect_disease": "中风"},
        ]
        retrieval_tests = []
        for tc in test_cases:
            hits = self.search(query=tc["query"], top_k=5)
            hit_diseases = set()
            for h in hits:
                hit_diseases.update(h.related_diseases)
            matched = tc["expect_disease"] in hit_diseases
            retrieval_tests.append({
                "query": tc["query"],
                "expect": tc["expect_disease"],
                "matched": matched,
                "top_results": [
                    {"title": h.title, "category": h.category, "diseases": h.related_diseases[:3]}
                    for h in hits[:3]
                ],
            })
        retrieval_accuracy = sum(1 for t in retrieval_tests if t["matched"]) / len(retrieval_tests)

        return {
            "total": total,
            "target": 2000,
            "target_met": total >= 2000,
            "category_distribution": dict(cat_dist),
            "disease_coverage": {
                "unique_diseases": len(disease_counter),
                "core_diseases": core_coverage,
                "core_covered": sum(1 for v in core_coverage.values() if v > 0),
                "core_total": len(core_diseases),
            },
            "confidence": {
                "min": round(min(confs), 2),
                "max": round(max(confs), 2),
                "avg": round(sum(confs) / total, 2),
                "bands": conf_bands,
                "high_confidence_rate": round(high_conf_rate, 3),
            },
            "traceability": {
                "has_original_text": has_original,
                "rate": round(traceability, 3),
            },
            "verified": {
                "count": verified,
                "rate": round(verified / total, 3),
            },
            "formula_count": has_formula,
            "cross_matrix": cross_matrix,
            "retrieval_test": {
                "cases": retrieval_tests,
                "accuracy": round(retrieval_accuracy, 3),
            },
            "engine": {
                "jieba": _HAS_JIEBA,
                "bm25": _HAS_BM25,
                "chroma": self._chroma_collection is not None,
            },
        }
        self._eval_cache = result
        return result


# 模块级单例
knowledge_service = KnowledgeService()
