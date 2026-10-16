<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getKnowledgeEvaluation, listKnowledgeEntries } from '../api'

const activeTab = ref<'list' | 'eval'>('list')

// ====== 条目列表 ======
const listLoading = ref(false)
const listData = ref<any[]>([])
const listTotal = ref(0)
const listPage = ref(1)
const listPageSize = ref(30)
const listPages = ref(0)
const filterCategory = ref('')
const filterKeyword = ref('')
const expandedRow = ref<string | null>(null)

async function fetchList() {
  listLoading.value = true
  try {
    const res = await listKnowledgeEntries({
      page: listPage.value,
      page_size: listPageSize.value,
      category: filterCategory.value || undefined,
      q: filterKeyword.value || undefined,
    })
    const d = res.data
    listData.value = d.items
    listTotal.value = d.total
    listPages.value = d.pages
  } finally {
    listLoading.value = false
  }
}

function onPageChange(page: number) {
  if (page < 1 || page > listPages.value) return
  listPage.value = page
  expandedRow.value = null
  fetchList()
}

function onFilter() {
  listPage.value = 1
  expandedRow.value = null
  fetchList()
}

function toggleExpand(id: string) {
  expandedRow.value = expandedRow.value === id ? null : id
}

// ====== 评估数据 ======
const evalLoading = ref(false)
const evalData = ref<any>(null)

async function loadEval() {
  if (evalData.value) return
  evalLoading.value = true
  try {
    const res = await getKnowledgeEvaluation()
    evalData.value = res.data
  } finally {
    evalLoading.value = false
  }
}

function switchTab(tab: 'list' | 'eval') {
  activeTab.value = tab
  if (tab === 'eval') loadEval()
}

const catColors: Record<string, string> = {
  '理': '#C8A45C',
  '法': '#5FB3A1',
  '方': '#9A2D2D',
  '药': '#4A90D9',
  '养生': '#B5463F',
}

const confBandColors: Record<string, string> = {
  '0.9-1.0': '#5FB3A1',
  '0.8-0.9': '#C8A45C',
  '0.7-0.8': '#4A90D9',
  '0.6-0.7': '#B5463F',
  '<0.6': '#9A2D2D',
}

const crossCategories = ['理', '法', '方', '药', '养生']

function crossCellClass(count: number): string {
  if (count >= 20) return 'cell-hot'
  if (count >= 10) return 'cell-warm'
  if (count >= 5) return 'cell-mild'
  if (count > 0) return 'cell-cool'
  return 'cell-empty'
}

function coreDiseaseSorted(evalD: any) {
  const cd = evalD.disease_coverage.core_diseases as Record<string, number>
  return Object.entries(cd).sort((a, b) => b[1] - a[1])
}

function maxDiseaseCount(evalD: any) {
  const sorted = coreDiseaseSorted(evalD)
  return sorted.length ? sorted[0][1] : 1
}

function printReport() {
  window.print()
}

function paginationRange(): number[] {
  const total = listPages.value
  const cur = listPage.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  let start = Math.max(1, cur - 3)
  let end = Math.min(total, cur + 3)
  if (cur <= 4) end = Math.min(7, total)
  if (cur >= total - 3) start = Math.max(1, total - 6)
  const pages: number[] = []
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
}

onMounted(() => {
  fetchList()
})
</script>

<template>
  <div class="kb-overview">
    <div class="page-header">
      <div>
        <h1 class="page-title">知识库总览</h1>
        <p class="page-subtitle">{{ listTotal }} 条结构化条目 · 基于《本草纲目》李时珍老年病学术思想</p>
      </div>
    </div>

    <!-- Tab切换 -->
    <div class="tab-bar">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'list' }"
        @click="switchTab('list')"
      >条目明细</button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'eval' }"
        @click="switchTab('eval')"
      >评估报告</button>
      <button
        v-if="activeTab === 'eval'"
        class="print-link no-print"
        @click="printReport"
      >导出PDF</button>
    </div>

    <!-- ====== Tab 1: 条目列表 ====== -->
    <div v-show="activeTab === 'list'" class="tab-panel list-panel">
      <!-- 筛选栏 -->
      <div class="list-toolbar">
        <div class="toolbar-left">
          <select v-model="filterCategory" class="filter-select" @change="onFilter">
            <option value="">全部分类</option>
            <option value="理">理</option>
            <option value="法">法</option>
            <option value="方">方</option>
            <option value="药">药</option>
            <option value="养生">养生</option>
          </select>
          <div class="search-box">
            <input
              v-model="filterKeyword"
              class="filter-input"
              placeholder="搜索标题关键词..."
              @keyup.enter="onFilter"
            />
            <button class="search-btn" @click="onFilter">搜索</button>
          </div>
        </div>
        <div class="toolbar-right">
          <span class="result-count tnum">{{ listTotal }} 条</span>
        </div>
      </div>

      <!-- 表格容器（固定高度内滚动） -->
      <div class="table-container" v-loading="listLoading">
        <table class="entries-table">
          <thead>
            <tr>
              <th class="th-id">编号</th>
              <th class="th-cat">类</th>
              <th class="th-title">标题</th>
              <th class="th-disease">关联病证</th>
              <th class="th-source">出处</th>
              <th class="th-conf">置信度</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="entry in listData" :key="entry.id">
              <tr class="entry-row" @click="toggleExpand(entry.id)" :class="{ expanded: expandedRow === entry.id }">
                <td class="td-id tnum">{{ entry.id }}</td>
                <td class="td-cat">
                  <span class="cat-dot" :style="{ background: catColors[entry.category] || '#999' }"></span>
                  {{ entry.category }}
                </td>
                <td class="td-title">{{ entry.title }}</td>
                <td class="td-disease">{{ (entry.related_diseases || []).slice(0, 2).join('、') }}</td>
                <td class="td-source">{{ entry.source?.volume || '' }}</td>
                <td class="td-conf tnum">
                  <span class="conf-pill" :class="entry.confidence >= 0.8 ? 'conf-high' : entry.confidence >= 0.7 ? 'conf-mid' : 'conf-low'">
                    {{ (entry.confidence * 100).toFixed(0) }}
                  </span>
                </td>
              </tr>
              <!-- 展开详情 -->
              <tr v-if="expandedRow === entry.id" class="detail-row">
                <td colspan="6">
                  <div class="detail-box">
                    <div v-if="entry.original_text" class="detail-field">
                      <span class="field-label">原文</span>
                      <span class="field-value serif">{{ entry.original_text }}</span>
                    </div>
                    <div v-if="entry.plain_explanation" class="detail-field">
                      <span class="field-label">释义</span>
                      <span class="field-value">{{ entry.plain_explanation }}</span>
                    </div>
                    <div v-if="entry.diagnosis_points" class="detail-field">
                      <span class="field-label">辨证</span>
                      <span class="field-value">{{ entry.diagnosis_points }}</span>
                    </div>
                    <div v-if="entry.treatment_method" class="detail-field">
                      <span class="field-label">治法</span>
                      <span class="field-value">{{ entry.treatment_method }}</span>
                    </div>
                    <div v-if="entry.formula && entry.formula.name" class="detail-field">
                      <span class="field-label">方剂</span>
                      <span class="field-value">
                        <b>{{ entry.formula.name }}</b>：{{ (entry.formula.composition || []).map((h: any) => `${h.herb}(${h.role})`).join('、') }}
                      </span>
                    </div>
                    <div v-if="entry.modern_mapping" class="detail-field">
                      <span class="field-label">对应</span>
                      <span class="field-value">{{ entry.modern_mapping }}</span>
                    </div>
                    <div v-if="(entry.tags || []).length" class="detail-field">
                      <span class="field-label">标签</span>
                      <span class="field-value">
                        <span v-for="tag in entry.tags" :key="tag" class="tag-chip">{{ tag }}</span>
                      </span>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="!listLoading && !listData.length">
              <td colspan="6" class="empty-row">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="pagination" v-if="listPages > 0">
        <button :disabled="listPage <= 1" @click="onPageChange(1)" class="pg-btn">首页</button>
        <button :disabled="listPage <= 1" @click="onPageChange(listPage - 1)" class="pg-btn">上一页</button>
        <div class="pg-numbers">
          <button
            v-for="p in paginationRange()"
            :key="p"
            class="pg-num"
            :class="{ 'pg-active': p === listPage }"
            @click="onPageChange(p)"
          >{{ p }}</button>
        </div>
        <button :disabled="listPage >= listPages" @click="onPageChange(listPage + 1)" class="pg-btn">下一页</button>
        <button :disabled="listPage >= listPages" @click="onPageChange(listPages)" class="pg-btn">末页</button>
        <span class="pg-info tnum">{{ listPage }}/{{ listPages }}</span>
      </div>
    </div>

    <!-- ====== Tab 2: 评估报告 ====== -->
    <div v-show="activeTab === 'eval'" class="tab-panel eval-panel" v-loading="evalLoading">
      <template v-if="evalData">
        <!-- 核心指标 -->
        <section class="metrics-row">
          <div class="metric-card navy-surface">
            <div class="metric-value tnum">{{ evalData.total }}</div>
            <div class="metric-label">知识条目</div>
            <div class="metric-tag tag-pass">目标 {{ evalData.target }}+ ✓</div>
          </div>
          <div class="metric-card navy-surface">
            <div class="metric-value tnum">{{ evalData.disease_coverage.core_covered }}/{{ evalData.disease_coverage.core_total }}</div>
            <div class="metric-label">核心病种</div>
            <div class="metric-tag tag-pass">{{ evalData.disease_coverage.unique_diseases }}种</div>
          </div>
          <div class="metric-card navy-surface">
            <div class="metric-value tnum">{{ (evalData.confidence.high_confidence_rate * 100).toFixed(0) }}%</div>
            <div class="metric-label">高置信率</div>
            <div class="metric-tag tag-pass">均值 {{ evalData.confidence.avg }}</div>
          </div>
          <div class="metric-card navy-surface">
            <div class="metric-value tnum">{{ (evalData.traceability.rate * 100).toFixed(0) }}%</div>
            <div class="metric-label">原文溯源</div>
            <div class="metric-tag tag-pass">{{ evalData.traceability.has_original_text }}条</div>
          </div>
          <div class="metric-card navy-surface">
            <div class="metric-value tnum">{{ (evalData.retrieval_test.accuracy * 100).toFixed(0) }}%</div>
            <div class="metric-label">检索准确</div>
            <div class="metric-tag tag-pass">{{ evalData.retrieval_test.cases.length }}组测试</div>
          </div>
        </section>

        <div class="eval-grid">
          <!-- 分类分布 -->
          <section class="card eval-card">
            <h3 class="eval-card-title">五类分布</h3>
            <div class="cat-bars">
              <div v-for="(count, cat) in evalData.category_distribution" :key="cat" class="cat-row">
                <span class="cat-name serif">{{ cat }}</span>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: (count / evalData.total * 100) + '%', background: catColors[cat as string] }"></div>
                </div>
                <span class="cat-num tnum">{{ count }}</span>
              </div>
            </div>
          </section>

          <!-- 置信度 -->
          <section class="card eval-card">
            <h3 class="eval-card-title">置信度分段</h3>
            <div class="cat-bars">
              <div v-for="(count, band) in evalData.confidence.bands" :key="band" class="cat-row">
                <span class="cat-name tnum" style="width:56px">{{ band }}</span>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: (count / evalData.total * 100) + '%', background: confBandColors[band as string] }"></div>
                </div>
                <span class="cat-num tnum">{{ count }}</span>
              </div>
            </div>
          </section>

          <!-- 核心病种 -->
          <section class="card eval-card">
            <h3 class="eval-card-title">核心病种覆盖</h3>
            <div class="cat-bars">
              <div v-for="[disease, count] in coreDiseaseSorted(evalData)" :key="disease" class="cat-row">
                <span class="cat-name" style="width:48px">{{ disease }}</span>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: (count / maxDiseaseCount(evalData) * 100) + '%', background: 'var(--gold)' }"></div>
                </div>
                <span class="cat-num tnum">{{ count }}</span>
              </div>
            </div>
          </section>

          <!-- 检索测试 -->
          <section class="card eval-card">
            <h3 class="eval-card-title">检索准确性</h3>
            <div class="test-list">
              <div v-for="(tc, i) in evalData.retrieval_test.cases" :key="i" class="test-item">
                <span class="test-badge" :class="tc.matched ? 'badge-pass' : 'badge-fail'">{{ tc.matched ? '✓' : '✗' }}</span>
                <div class="test-body">
                  <div class="test-q">{{ tc.query }}</div>
                  <div class="test-hits">
                    <span v-for="(r, j) in tc.top_results" :key="j" class="hit-tag">
                      [{{ r.category }}] {{ r.title.length > 16 ? r.title.slice(0, 16) + '…' : r.title }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- 交叉矩阵 -->
          <section class="card eval-card eval-card-wide">
            <h3 class="eval-card-title">病种×分类交叉覆盖</h3>
            <div class="matrix-wrap">
              <table class="cross-matrix">
                <thead>
                  <tr>
                    <th>病种</th>
                    <th v-for="cat in crossCategories" :key="cat">{{ cat }}</th>
                    <th>合计</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="[disease] in coreDiseaseSorted(evalData)" :key="disease">
                    <td class="m-disease">{{ disease }}</td>
                    <td v-for="cat in crossCategories" :key="cat" :class="crossCellClass(evalData.cross_matrix[disease]?.[cat] || 0)">
                      {{ evalData.cross_matrix[disease]?.[cat] || 0 }}
                    </td>
                    <td class="m-total tnum">{{ crossCategories.reduce((s: number, c: string) => s + (evalData.cross_matrix[disease]?.[c] || 0), 0) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- 引擎与其他 -->
          <section class="card eval-card">
            <h3 class="eval-card-title">系统状态</h3>
            <div class="status-list">
              <div class="status-row">
                <span class="dot" :class="evalData.engine.jieba ? 'dot-on' : 'dot-off'"></span>
                <span>结巴分词</span>
                <span class="status-val">{{ evalData.engine.jieba ? '就绪' : '—' }}</span>
              </div>
              <div class="status-row">
                <span class="dot" :class="evalData.engine.bm25 ? 'dot-on' : 'dot-off'"></span>
                <span>BM25 关键词检索</span>
                <span class="status-val">{{ evalData.engine.bm25 ? '就绪' : '—' }}</span>
              </div>
              <div class="status-row">
                <span class="dot" :class="evalData.engine.chroma ? 'dot-on' : 'dot-off'"></span>
                <span>ChromaDB 向量检索</span>
                <span class="status-val">{{ evalData.engine.chroma ? '就绪' : '—' }}</span>
              </div>
              <div class="status-row border-t">
                <span></span>
                <span>含方剂条目</span>
                <span class="status-val tnum">{{ evalData.formula_count }}</span>
              </div>
              <div class="status-row">
                <span></span>
                <span>已人工验证</span>
                <span class="status-val tnum">{{ evalData.verified.count }} ({{ (evalData.verified.rate * 100).toFixed(0) }}%)</span>
              </div>
              <div class="status-row">
                <span></span>
                <span>嵌入模型</span>
                <span class="status-val">text2vec-base-chinese</span>
              </div>
              <div class="status-row">
                <span></span>
                <span>混合权重</span>
                <span class="status-val">向量60% + BM25 40%</span>
              </div>
            </div>
          </section>
        </div>

        <div class="eval-footer">
          本评估报告由系统自动生成。数据源自《本草纲目》原文提取与结构化整理。本系统为学术研究与辅助参考，不替代执业医师面诊。
        </div>
      </template>
    </div>
  </div>
</template>


<style scoped>
.kb-overview {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.page-header {
  flex-shrink: 0;
  margin-bottom: 16px;
}

/* Tab栏 */
.tab-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 16px;
  border-bottom: 2px solid var(--border-paper);
  padding-bottom: 0;
}

.tab-btn {
  padding: 8px 20px;
  border: none;
  background: none;
  font-size: 15px;
  font-family: var(--font-sans);
  color: var(--ink-2);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}

.tab-btn.active {
  color: var(--ink);
  font-weight: 600;
  border-bottom-color: var(--gold);
}

.tab-btn:hover:not(.active) {
  color: var(--ink);
}

.print-link {
  margin-left: auto;
  padding: 5px 14px;
  background: var(--cinnabar);
  color: #FBF7EE;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  margin-bottom: 4px;
}

/* Tab panel */
.tab-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* ====== 列表面板 ====== */
.list-panel {
  gap: 0;
}

.list-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  gap: 8px;
  align-items: center;
}

.filter-select {
  padding: 6px 10px;
  border: 1px solid var(--border-paper);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--paper-card);
  color: var(--ink);
}

.search-box {
  display: flex;
  border: 1px solid var(--border-paper);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.filter-input {
  padding: 6px 12px;
  border: none;
  font-size: 13px;
  background: var(--paper-card);
  color: var(--ink);
  width: 180px;
  outline: none;
}

.search-btn {
  padding: 6px 14px;
  background: var(--gold);
  color: #fff;
  border: none;
  font-size: 12px;
  cursor: pointer;
}

.search-btn:hover { background: var(--gold-soft); }

.result-count {
  font-size: 13px;
  color: var(--ink-2);
}

/* 表格容器 */
.table-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  border: 1px solid var(--border-paper);
  border-radius: var(--radius-sm);
  background: var(--paper-card);
}

.entries-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.entries-table thead {
  position: sticky;
  top: 0;
  z-index: 2;
}

.entries-table th {
  background: var(--paper-sunken);
  font-weight: 600;
  font-size: 12px;
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-paper);
  white-space: nowrap;
}

.entries-table td {
  padding: 9px 12px;
  border-bottom: 1px solid rgba(31, 27, 22, 0.06);
}

.entry-row {
  cursor: pointer;
  transition: background 0.12s;
}

.entry-row:hover { background: rgba(200, 164, 92, 0.05); }
.entry-row.expanded { background: rgba(200, 164, 92, 0.08); }

.th-id, .td-id { width: 110px; font-size: 11px; color: var(--ink-3); }
.th-cat, .td-cat { width: 50px; white-space: nowrap; }
.th-title, .td-title { font-weight: 500; }
.th-disease, .td-disease { width: 130px; font-size: 12px; color: var(--ink-2); }
.th-source, .td-source { width: 100px; font-size: 12px; color: var(--ink-2); }
.th-conf, .td-conf { width: 54px; text-align: center; }

.cat-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}

.conf-pill {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
}

.conf-high { background: rgba(95, 179, 161, 0.15); color: #2d7d6d; }
.conf-mid { background: rgba(200, 164, 92, 0.15); color: #8a6d2c; }
.conf-low { background: rgba(154, 45, 45, 0.12); color: var(--cinnabar); }

/* 展开详情行 */
.detail-row td {
  padding: 0 !important;
  background: rgba(200, 164, 92, 0.03);
  border-bottom: 2px solid var(--gold-soft);
}

.detail-box {
  padding: 12px 16px 12px 122px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-field {
  display: flex;
  gap: 8px;
  line-height: 1.7;
  font-size: 13px;
}

.field-label {
  flex-shrink: 0;
  width: 44px;
  text-align: right;
  color: var(--ink-3);
  font-size: 12px;
}

.field-value { flex: 1; color: var(--ink); }

.tag-chip {
  display: inline-block;
  padding: 0 7px;
  margin: 0 3px 2px 0;
  background: var(--paper-sunken);
  border-radius: 8px;
  font-size: 11px;
  color: var(--ink-2);
}

.empty-row {
  text-align: center;
  padding: 40px 0 !important;
  color: var(--ink-3);
}

/* 分页 */
.pagination {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 12px 0 4px;
}

.pg-btn {
  padding: 5px 12px;
  background: var(--paper-card);
  border: 1px solid var(--border-paper);
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  color: var(--ink);
}

.pg-btn:hover:not(:disabled) { border-color: var(--gold); color: var(--gold); }
.pg-btn:disabled { opacity: 0.35; cursor: default; }

.pg-numbers {
  display: flex;
  gap: 2px;
}

.pg-num {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  color: var(--ink-2);
  background: none;
}

.pg-num:hover { background: var(--paper-sunken); }
.pg-num.pg-active { background: var(--gold); color: #fff; font-weight: 600; border-color: var(--gold); }

.pg-info {
  margin-left: 8px;
  font-size: 12px;
  color: var(--ink-3);
}

/* ====== 评估面板 ====== */
.eval-panel {
  overflow-y: auto;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.metric-card {
  padding: 16px 12px;
  text-align: center;
}

.metric-value {
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 700;
  color: var(--gold);
  line-height: 1.2;
}

.metric-label {
  font-size: 12px;
  color: var(--on-navy-2);
  margin-top: 2px;
}

.metric-tag {
  display: inline-block;
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 8px;
  margin-top: 6px;
}

.tag-pass { background: rgba(95, 179, 161, 0.2); color: var(--jade); }

/* 评估网格 */
.eval-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.eval-card {
  padding: 16px 20px;
}

.eval-card-wide {
  grid-column: 1 / -1;
}

.eval-card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid var(--gold);
}

/* 条形图通用 */
.cat-bars { display: flex; flex-direction: column; gap: 7px; }

.cat-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cat-name {
  width: 36px;
  text-align: right;
  font-size: 13px;
  flex-shrink: 0;
}

.bar-track {
  flex: 1;
  height: 16px;
  background: var(--paper-sunken);
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.cat-num {
  width: 36px;
  text-align: right;
  font-size: 12px;
  color: var(--ink-2);
}

/* 检索测试 */
.test-list { display: flex; flex-direction: column; gap: 10px; }

.test-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.test-badge {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
}

.badge-pass { background: rgba(95, 179, 161, 0.2); color: #2d7d6d; }
.badge-fail { background: rgba(154, 45, 45, 0.15); color: var(--cinnabar); }

.test-body { flex: 1; }
.test-q { font-size: 13px; font-weight: 500; margin-bottom: 3px; }
.test-hits { display: flex; flex-wrap: wrap; gap: 4px; }
.hit-tag {
  font-size: 11px;
  color: var(--ink-3);
  background: var(--paper-sunken);
  padding: 1px 6px;
  border-radius: 4px;
}

/* 交叉矩阵 */
.matrix-wrap { overflow-x: auto; }

.cross-matrix {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.cross-matrix th, .cross-matrix td {
  padding: 5px 8px;
  text-align: center;
  border: 1px solid var(--border-paper);
}

.cross-matrix th { background: var(--paper-sunken); font-weight: 600; }
.m-disease { text-align: left !important; font-weight: 500; white-space: nowrap; }
.m-total { font-weight: 600; background: var(--paper-sunken); }

.cell-hot { background: rgba(200, 164, 92, 0.35); font-weight: 600; }
.cell-warm { background: rgba(200, 164, 92, 0.18); }
.cell-mild { background: rgba(95, 179, 161, 0.12); }
.cell-cool { background: rgba(74, 144, 217, 0.08); }
.cell-empty { color: var(--ink-3); }

/* 状态列表 */
.status-list { display: flex; flex-direction: column; gap: 8px; }

.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.status-row.border-t { border-top: 1px solid var(--border-paper); padding-top: 8px; margin-top: 4px; }
.status-val { margin-left: auto; font-size: 12px; color: var(--ink-2); }

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-on { background: var(--jade); box-shadow: 0 0 5px rgba(95, 179, 161, 0.4); }
.dot-off { background: #ccc; }

.eval-footer {
  text-align: center;
  font-size: 11px;
  color: var(--ink-3);
  padding: 14px;
  background: var(--paper-sunken);
  border-radius: var(--radius-sm);
}

/* 响应式 */
@media (max-width: 900px) {
  .metrics-row { grid-template-columns: repeat(3, 1fr); }
  .eval-grid { grid-template-columns: 1fr; }
  .detail-box { padding-left: 16px; }
}

@media (max-width: 600px) {
  .metrics-row { grid-template-columns: repeat(2, 1fr); }
  .list-toolbar { flex-direction: column; align-items: stretch; }
  .td-disease, .th-disease, .td-source, .th-source { display: none; }
}

/* 打印 */
@media print {
  .no-print { display: none !important; }
  .tab-bar { display: none; }
  .list-panel { display: none !important; }
  .eval-panel { display: block !important; overflow: visible; }
  .navy-surface { background: #f5f5f5 !important; color: #333 !important; }
  .metric-value { color: #333 !important; }
  .metric-label { color: #666 !important; }
  .card { box-shadow: none; border: 1px solid #ddd; break-inside: avoid; }
}
</style>
