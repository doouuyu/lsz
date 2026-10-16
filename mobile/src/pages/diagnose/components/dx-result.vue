<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import type { Evidence, Herb, Role, SourceEntry, ViewModel } from "../types";
import { useRoleStore } from "@/stores/role";

/**
 * 辨证结果 · 藏青竖向长卷。渲染后端 8 步辨证（经 adaptResult → ViewModel）。
 * 角色自适应：role 取自全局 store；切换 role 由父页 switchRole 重新请求后端（切提示词）并按 role 缓存，
 * 本组件只负责发出切换意图（emit role-change）与渲染当前 vm，逻辑沉淀在 useDiagnose/store（便于老年版 dxe-result 复用）。
 * 交互重点：
 *  - 角色 segmented（患/医/研）：内容随后端按角色生成；研究者额外展开「理论溯源」节。
 *  - 步骤锚点 chips：scroll-into-view 跳转。
 *  - 各步逐条淡入（stagger）。
 *  - 经典印证 → 点开宣纸原文 bottom sheet（优先取 sources 里同 entry_id 的原文/白话）。
 */
const props = defineProps<{
  vm: ViewModel;
  chief: string;
  sources: SourceEntry[];
  hasLab?: boolean; // 本次辨证是否纳入了化验单 → 顶部显示「已纳入化验单」标识
  labFindings?: string; // 后端视觉模型实际读取到的化验单要点 → 结果页展开展示，让用户直观看到「确实读了」
  labUnreadable?: boolean; // 带了化验单但未能识别 → 给「未能识别·建议重拍」提示
  roleSwitching?: boolean; // 切角色重新请求后端中 → 顶部 segmented 锁定 + 轻 loading
}>();

const emit = defineEmits<{
  (e: "restart"): void;
  (e: "export"): void;
  (e: "role-change", role: Role): void; // 父页据此调 switchRole（重新请求 + 缓存）
}>();

const roleStore = useRoleStore();
const { role } = storeToRefs(roleStore);
// 后端已按角色切提示词生成（患者版剂量本就为空）；showDosage 仅用于朗读叙述与剂量列的稳妥兜底。
const showDosage = computed(() => role.value !== "patient");

const SECTIONS = computed(() => {
  const base = [
    { i: 1, title: "症状归纳" },
    { i: 2, title: "病位病性" },
    { i: 3, title: "证型辨别" },
    { i: 4, title: "经典印证" },
    { i: 5, title: "治法确立" },
    { i: 6, title: "方药配伍" },
    { i: 7, title: "调护医嘱" },
  ];
  // 研究者版多一个「理论溯源」锚点（id=step-8）
  if (props.vm.research) base.push({ i: 8, title: "理论溯源" });
  return base;
});

const scrollIntoId = ref("");
function jumpTo(i: number) {
  scrollIntoId.value = "";
  setTimeout(() => (scrollIntoId.value = `step-${i}`), 20);
}

const confidence = computed(() => {
  const v = props.vm.confidence ?? 0;
  if (v >= 75) return { label: "高", cls: "high" };
  if (v >= 50) return { label: "中", cls: "mid" };
  return { label: "参考", cls: "low" };
});

// 君臣佐使分组
const groups = computed(() => {
  const hs = props.vm.formula.herbs;
  const pick = (r: string) => hs.filter((h) => h.role.includes(r));
  // cls 用拉丁字母（WXSS 选择器不支持中文类名）；key 仅作徽标显示文字
  return [
    { key: "君", cls: "jun", herbs: pick("君") },
    { key: "臣", cls: "chen", herbs: pick("臣") },
    { key: "佐", cls: "zuo", herbs: pick("佐") },
    { key: "使", cls: "shi", herbs: pick("使") },
  ].filter((g) => g.herbs.length);
});
const otherHerbs = computed(() =>
  props.vm.formula.herbs.filter((h: Herb) => !/[君臣佐使]/.test(h.role))
);

const careItems = computed(() => {
  const c = props.vm.care;
  return [
    { seal: "忌", label: "用药禁忌", text: c.contraindication },
    { seal: "食", label: "食疗建议", text: c.diet },
    { seal: "居", label: "起居调护", text: c.lifestyle },
    { seal: "功", label: "简易功法", text: c.exercise },
  ].filter((x) => x.text);
});

/* 化验单要点展开态（默认展开，让用户第一眼看到「读了」） */
const labOpen = ref(true);

/* 溯源 sheet */
const srcShow = ref(false);
const activeSrc = ref<{ title: string; source: string; original: string; plain: string } | null>(
  null
);
function openEvidence(ev: Evidence) {
  const hit = ev.entry_id ? props.sources.find((s) => s.id === ev.entry_id) : undefined;
  activeSrc.value = {
    title: hit?.title || ev.source || "经典出处",
    source: ev.source || [hit?.source?.book, hit?.source?.volume, hit?.source?.section].filter(Boolean).join("·"),
    original: hit?.original_text || ev.text || "",
    plain: hit?.plain_explanation || "",
  };
  srcShow.value = true;
}

/**
 * 朗读叙述：把 VM 拼成一段通顺、适合朗读的中文，按 8 步顺序。
 * 尊重 role：患者视角不读出药物剂量与配伍理由，只读方名与整体治法/调护；医师/研究者读完整。
 * 空字段跳过，不读出「—」或占位。依赖 role.value，role 切换会重算。
 */
const narration = computed(() => {
  const vm = props.vm;
  const full = role.value !== "patient"; // 医/研：可读剂量与配伍
  const parts: string[] = [];

  if (props.chief?.trim()) parts.push(`主诉：${props.chief.trim()}。`);
  if (vm.summary?.trim()) parts.push(`症状归纳：${vm.summary.trim()}。`);

  // 病位病性
  const loc: string[] = [];
  const wei = (vm.location?.病位 || []).filter(Boolean);
  const xing = (vm.location?.病性 || []).filter(Boolean);
  if (wei.length) loc.push(`病位在${wei.join("、")}`);
  if (xing.length) loc.push(`病性属${xing.join("、")}`);
  if (vm.location?.气血津液?.trim()) loc.push(`气血津液方面，${vm.location.气血津液.trim()}`);
  if (loc.length) parts.push(`病位病性：${loc.join("，")}。`);

  // 证型辨别
  const zheng: string[] = [];
  if (vm.primary?.trim()) zheng.push(`主证为${vm.primary.trim()}`);
  const conc = (vm.concurrent || []).filter(Boolean);
  if (conc.length) zheng.push(`兼有${conc.join("、")}`);
  if (zheng.length) parts.push(`证型辨别：${zheng.join("，")}。`);

  if (vm.treatment?.trim()) parts.push(`治法：${vm.treatment.trim()}。`);

  // 方药
  const fx: string[] = [];
  if (vm.formula?.name?.trim()) fx.push(`选用${vm.formula.name.trim()}`);
  if (full) {
    const herbLines = (vm.formula?.herbs || [])
      .filter((h) => h.herb)
      .map((h) => {
        const seg = [h.herb.trim()];
        if (h.dosage?.trim()) seg.push(h.dosage.trim());
        if (h.reason?.trim()) seg.push(`，${h.reason.trim()}`);
        return seg.join(" ");
      });
    if (herbLines.length) fx.push(`组成为${herbLines.join("；")}`);
    if (vm.formula?.modification?.trim()) fx.push(`随症加减：${vm.formula.modification.trim()}`);
  }
  if (fx.length) parts.push(`方药：${fx.join("。")}。`);

  // 调护医嘱
  const careSeg: string[] = [];
  const c = vm.care;
  if (c?.contraindication?.trim()) careSeg.push(`用药禁忌，${c.contraindication.trim()}`);
  if (c?.diet?.trim()) careSeg.push(`食疗建议，${c.diet.trim()}`);
  if (c?.lifestyle?.trim()) careSeg.push(`起居调护，${c.lifestyle.trim()}`);
  if (c?.exercise?.trim()) careSeg.push(`简易功法，${c.exercise.trim()}`);
  if (careSeg.length) parts.push(`调护医嘱：${careSeg.join("；")}。`);

  // 理论溯源（研究者版）：读出溯源与流派分析，引证仅读出处名
  if (vm.research) {
    const r = vm.research;
    if (r.theoryOrigin?.trim()) parts.push(`理论溯源：${r.theoryOrigin.trim()}。`);
    const refs = r.citations.map((c) => c.ref).filter(Boolean);
    if (refs.length) parts.push(`文献引证：${refs.join("、")}。`);
    if (r.schools?.trim()) parts.push(`学术流派：${r.schools.trim()}。`);
  }

  if (vm.disclaimer?.trim()) parts.push(vm.disclaimer.trim());

  return parts.join("");
});
</script>

<template>
  <view class="rs gf-navy">
    <!-- 顶部：角色 + 锚点 -->
    <view class="rs__top">
      <view class="rs__top-row">
        <view class="rs__roles">
          <view class="rs__role active">
            报告视角：{{ role === "patient" ? "患者" : role === "doctor" ? "医师" : "研究者" }}（已锁定）
          </view>
        </view>
        <gf-speaker tone="navy" :text="narration" label="朗读报告" class="rs__speak" />
      </view>
      <scroll-view scroll-x class="rs__anchors" :show-scrollbar="false">
        <view class="rs__anchors-row">
          <view v-for="s in SECTIONS" :key="s.i" class="rs__anchor" @tap="jumpTo(s.i)">
            {{ s.i }} {{ s.title }}
          </view>
        </view>
      </scroll-view>
    </view>

    <scroll-view scroll-y class="rs__scroll" :scroll-into-view="scrollIntoId" :scroll-with-animation="true">
      <view class="rs__banner">
        <gf-icon name="check" :size="34" color="#5FB3A1" />
        <text>四诊已明 · 辨证如下</text>
      </view>
      <view class="rs__chief gf-on-navy-2">主诉：{{ chief }}</view>

      <!-- ① 症状归纳 -->
      <view id="step-1" class="rs__step" :style="{ animationDelay: '0s' }">
        <view class="rs__step-head">
          <view class="rs__seal gf-seal gf-serif">1</view>
          <view class="rs__step-title gf-serif">症状归纳</view>
          <view v-if="hasLab" class="rs__lab-flag">
            <gf-icon name="file" :size="24" color="#5FB3A1" /><text>已纳入医疗附件</text>
          </view>
        </view>
        <view class="rs__para">{{ vm.summary || "—" }}</view>
        <!-- 化验单要点：让用户直观看到「确实读取并纳入了化验单」 -->
        <view v-if="labFindings" class="rs__lab">
          <view class="rs__lab-head" @tap="labOpen = !labOpen">
            <gf-icon name="file" :size="26" color="#5FB3A1" />
            <text class="rs__lab-h gf-serif">化验单要点（已读取并纳入辨证）</text>
            <text class="rs__lab-toggle gf-on-navy-2">{{ labOpen ? "收起" : "展开" }}</text>
          </view>
          <view v-if="labOpen" class="rs__lab-body">{{ labFindings }}</view>
        </view>
        <view v-else-if="labUnreadable" class="rs__lab is-warn">
          <gf-icon name="file" :size="26" color="#C8923B" />
          <text class="rs__lab-warn">化验单未能识别，本次未纳入。建议重拍更清晰、光线充足的照片再试。</text>
        </view>
      </view>

      <!-- ② 病位病性 -->
      <view id="step-2" class="rs__step" :style="{ animationDelay: '0.08s' }">
        <view class="rs__step-head"><view class="rs__seal gf-seal gf-serif">2</view><view class="rs__step-title gf-serif">病位病性</view></view>
        <view class="rs__kv">
          <text class="rs__k gf-on-navy-2">病位</text>
          <view class="rs__tags"><text v-for="(t, i) in vm.location.病位" :key="i" class="rs__tag">{{ t }}</text></view>
        </view>
        <view class="rs__kv">
          <text class="rs__k gf-on-navy-2">病性</text>
          <view class="rs__tags"><text v-for="(t, i) in vm.location.病性" :key="i" class="rs__tag rs__tag--jade">{{ t }}</text></view>
        </view>
        <view v-if="vm.location.气血津液" class="rs__para">气血津液：{{ vm.location.气血津液 }}</view>
      </view>

      <!-- ③ 证型辨别 -->
      <view id="step-3" class="rs__step" :style="{ animationDelay: '0.16s' }">
        <view class="rs__step-head">
          <view class="rs__seal gf-seal gf-serif">3</view><view class="rs__step-title gf-serif">证型辨别</view>
          <view class="rs__conf" :class="confidence.cls">把握 {{ confidence.label }} · {{ vm.confidence }}%</view>
        </view>
        <view class="rs__primary">主证：<text class="gf-gold">{{ vm.primary }}</text></view>
        <view v-if="vm.concurrent.length" class="rs__kv">
          <text class="rs__k gf-on-navy-2">兼证</text>
          <view class="rs__tags"><text v-for="(t, i) in vm.concurrent" :key="i" class="rs__tag">{{ t }}</text></view>
        </view>
        <!-- 候选证型 bar（替代雷达，无需 ECharts） -->
        <view class="rs__bars">
          <view v-for="(c, i) in vm.candidates" :key="i" class="rs__bar">
            <view class="rs__bar-label">
              <text class="rs__bar-name">{{ c.name }}</text>
              <text class="rs__bar-score gf-tnum">{{ c.score }}%</text>
            </view>
            <view class="rs__bar-track">
              <view class="rs__bar-fill" :class="{ 'is-primary': i === 0 }" :style="{ width: c.score + '%' }" />
            </view>
          </view>
        </view>
      </view>

      <!-- ④ 经典印证 -->
      <view id="step-4" class="rs__step" :style="{ animationDelay: '0.24s' }">
        <view class="rs__step-head"><view class="rs__seal gf-seal gf-serif">4</view><view class="rs__step-title gf-serif">经典印证</view></view>
        <view v-if="vm.evidence.length" class="rs__evid">
          <view
            v-for="(ev, i) in vm.evidence"
            :key="i"
            class="rs__evid-item"
            hover-class="rs__evid-item--hover"
            @tap="openEvidence(ev)"
          >
            <gf-icon name="book" :size="28" color="#C8A45C" />
            <view class="rs__evid-body">
              <view class="rs__evid-text">{{ ev.text }}</view>
              <view class="rs__evid-src gf-on-navy-2">{{ ev.source }}</view>
            </view>
          </view>
        </view>
        <view v-else class="rs__para gf-on-navy-2">—</view>
      </view>

      <!-- ⑤ 治法确立 -->
      <view id="step-5" class="rs__step" :style="{ animationDelay: '0.32s' }">
        <view class="rs__step-head"><view class="rs__seal gf-seal gf-serif">5</view><view class="rs__step-title gf-serif">治法确立</view></view>
        <view class="rs__para">{{ vm.treatment || "—" }}</view>
      </view>

      <!-- ⑥ 方药配伍 -->
      <view id="step-6" class="rs__step" :style="{ animationDelay: '0.4s' }">
        <view class="rs__step-head">
          <view class="rs__seal gf-seal gf-serif">6</view><view class="rs__step-title gf-serif">方药配伍</view>
          <view v-if="!showDosage" class="rs__role-tip gf-on-navy-2">患者视角已隐藏剂量</view>
        </view>
        <view v-if="vm.formula.name" class="rs__formula-name gf-gold gf-serif">{{ vm.formula.name }}</view>
        <view class="rs__jun">
          <view v-for="g in groups" :key="g.key" class="rs__jun-group">
            <view class="rs__jun-badge" :class="'rs__jun-badge--' + g.cls">{{ g.key }}</view>
            <view class="rs__jun-herbs">
              <view v-for="(h, i) in g.herbs" :key="i" class="rs__herb">
                <text class="rs__herb-name">{{ h.herb }}</text>
                <text v-if="showDosage && h.dosage" class="rs__herb-dose gf-tnum">{{ h.dosage }}</text>
                <text v-if="showDosage && h.reason" class="rs__herb-reason gf-on-navy-2">{{ h.reason }}</text>
              </view>
            </view>
          </view>
          <view v-if="otherHerbs.length" class="rs__jun-group">
            <view class="rs__jun-badge rs__jun-badge--other">药</view>
            <view class="rs__jun-herbs">
              <view v-for="(h, i) in otherHerbs" :key="i" class="rs__herb">
                <text class="rs__herb-name">{{ h.herb }}</text>
                <text v-if="showDosage && h.dosage" class="rs__herb-dose gf-tnum">{{ h.dosage }}</text>
              </view>
            </view>
          </view>
        </view>
        <view v-if="vm.formula.modification" class="rs__para rs__mod">随症加减：{{ vm.formula.modification }}</view>
      </view>

      <!-- ⑦ 调护医嘱 -->
      <view id="step-7" class="rs__step" :style="{ animationDelay: '0.48s' }">
        <view class="rs__step-head"><view class="rs__seal gf-seal gf-serif">7</view><view class="rs__step-title gf-serif">调护医嘱</view></view>
        <view class="rs__care">
          <view v-for="(c, i) in careItems" :key="i" class="rs__care-item">
            <view class="rs__care-seal gf-seal gf-serif">{{ c.seal }}</view>
            <view class="rs__care-body">
              <view class="rs__care-label gf-on-navy-2">{{ c.label }}</view>
              <view class="rs__para">{{ c.text }}</view>
            </view>
          </view>
        </view>
      </view>

      <!-- ⑧ 理论溯源（研究者专属：后端 step9_research，其余角色不返回此节） -->
      <view
        v-if="vm.research"
        id="step-8"
        class="rs__step rs__step--research"
        :style="{ animationDelay: '0.56s' }"
      >
        <view class="rs__step-head">
          <view class="rs__seal gf-seal gf-serif">研</view>
          <view class="rs__step-title gf-serif">理论溯源</view>
        </view>
        <view v-if="vm.research.theoryOrigin" class="rs__para">{{ vm.research.theoryOrigin }}</view>
        <view v-if="vm.research.citations.length" class="rs__cites">
          <view class="rs__cites-label gf-on-navy-2">文献引证</view>
          <view v-for="(c, i) in vm.research.citations" :key="i" class="rs__cite">
            <text class="rs__cite-ref gf-gold">{{ c.ref }}</text>
            <text v-if="c.point" class="rs__cite-point">{{ c.point }}</text>
          </view>
        </view>
        <view v-if="vm.research.schools" class="rs__cites">
          <view class="rs__cites-label gf-on-navy-2">学术流派</view>
          <view class="rs__para">{{ vm.research.schools }}</view>
        </view>
      </view>

      <!-- footer -->
      <view class="rs__footer">
        <view class="rs__btn rs__btn--primary" hover-class="rs__btn--hover" @tap="emit('export')">
          <gf-icon name="report" :size="34" color="#FBF7EE" /><text>导出脉案报告</text>
        </view>
        <view class="rs__btn rs__btn--ghost" hover-class="rs__btn--hover" @tap="emit('restart')">重新辨证</view>
      </view>
      <view class="rs__disclaimer">{{ vm.disclaimer }}</view>
    </scroll-view>

    <!-- 溯源原文 sheet -->
    <wd-popup
      v-model="srcShow"
      position="bottom"
      :safe-area-inset-bottom="true"
      custom-style="border-radius:24rpx 24rpx 0 0;background:#F3ECDD;"
    >
      <!-- @touchmove.stop：面板手势不穿透到下层页面（内部 scroll-view 原生滚动不受影响） -->
      <view class="src" @touchmove.stop>
        <view class="src__bar">
          <view class="src__title gf-serif">{{ activeSrc?.title }}</view>
          <view class="src__close" @tap="srcShow = false"><gf-icon name="close" :size="36" color="#5C5345" /></view>
        </view>
        <scroll-view scroll-y class="src__scroll">
          <view v-if="activeSrc?.source" class="src__meta gf-ink-3">{{ activeSrc.source }}</view>
          <view class="src__orig-label gf-ink-3">原文</view>
          <view class="src__orig gf-serif">{{ activeSrc?.original || "—" }}</view>
          <template v-if="activeSrc?.plain">
            <view class="gf-divider" />
            <view class="src__plain-label gf-ink-3">白话</view>
            <view class="src__plain">{{ activeSrc.plain }}</view>
          </template>
        </scroll-view>
      </view>
    </wd-popup>

    <!-- 切角色重新请求后端时的轻覆盖层（不离开结果页，只盖一层 + 提示「按X重新生成」） -->
    <view v-if="roleSwitching" class="rs__switching" @touchmove.stop.prevent>
      <view class="rs__switching-card">
        <view class="rs__switching-dots">
          <view
            v-for="i in 3"
            :key="i"
            class="rs__switching-dot"
            :style="{ animationDelay: i * 0.16 + 's' }"
          />
        </view>
        <text class="rs__switching-txt">正在为{{
          role === "patient" ? "患者" : role === "doctor" ? "医师" : "研究者"
        }}重新生成…</text>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.rs {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-radius: 0;

  &__top {
    padding: 16rpx 32rpx 12rpx;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  &__top-row {
    display: flex;
    align-items: center;
    gap: 16rpx;
  }
  &__roles {
    display: flex;
    flex: 1;
    min-width: 0;
    background: rgba(255, 255, 255, 0.06);
    border-radius: $radius-sm;
    padding: 6rpx;
    box-sizing: border-box;
    /* 切角色请求途中：整条 segmented 降透明并禁点，避免连点叠请求 */
    &.is-switching {
      opacity: 0.55;
      pointer-events: none;
    }
  }
  &__speak {
    flex-shrink: 0;
  }
  &__role {
    flex: 1;
    text-align: center;
    line-height: 64rpx;
    font-size: 28rpx;
    color: $on-navy-2;
    border-radius: 12rpx;
    &.active {
      background: $cinnabar;
      color: $paper-card;
      font-weight: 600;
    }
  }
  &__anchors {
    white-space: nowrap;
    margin-top: 16rpx;
  }
  &__anchors-row {
    display: inline-flex;
    gap: 12rpx;
  }
  &__anchor {
    flex-shrink: 0;
    padding: 8rpx 20rpx;
    font-size: 24rpx;
    color: $on-navy-2;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 999rpx;
  }

  &__scroll {
    flex: 1;
    min-height: 0;
    padding: 24rpx 32rpx env(safe-area-inset-bottom);
    box-sizing: border-box;
  }
  &__banner {
    display: flex;
    align-items: center;
    gap: 12rpx;
    font-size: 30rpx;
    color: $jade;
    font-family: $font-serif;
    margin-bottom: 8rpx;
  }
  &__chief {
    font-size: 26rpx;
    margin-bottom: 20rpx;
  }

  &__step {
    padding: 28rpx;
    margin-bottom: 24rpx;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: $radius;
    opacity: 0;
    transform: translateY(16rpx);
    animation: stepIn 0.4s ease forwards;
  }
  &__step-head {
    display: flex;
    align-items: center;
    gap: 16rpx;
    margin-bottom: 16rpx;
  }
  &__seal {
    width: 56rpx;
    height: 56rpx;
    font-size: 30rpx;
  }
  &__step-title {
    font-size: 34rpx;
    font-weight: 700;
    color: $on-navy;
  }
  &__conf,
  &__role-tip {
    margin-left: auto;
    font-size: 22rpx;
    padding: 4rpx 16rpx;
    border-radius: 999rpx;
  }
  /* 「已纳入化验单」标识：玉色描边小药丸，钉在步骤头行尾 */
  &__lab-flag {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 6rpx;
    font-size: 22rpx;
    padding: 4rpx 16rpx;
    border-radius: 999rpx;
    color: $jade;
    background: rgba(95, 179, 161, 0.14);
    border: 1px solid rgba(95, 179, 161, 0.4);
  }
  &__conf {
    border: 1px solid;
    &.high { color: $jade; border-color: $jade; }
    &.mid { color: $gold; border-color: $gold; }
    &.low { color: $on-navy-2; border-color: rgba(255, 255, 255, 0.3); }
  }

  &__para {
    font-size: 30rpx;
    line-height: 1.7;
    color: $on-navy;
    margin-bottom: 6rpx;
  }
  /* 化验单要点卡：藏青面上的玉色描边小卡，证明「确实读了」 */
  &__lab {
    margin-top: 14rpx;
    padding: 16rpx 20rpx;
    border: 1rpx solid rgba(95, 179, 161, 0.45);
    border-radius: 14rpx;
    background: rgba(95, 179, 161, 0.08);
    &.is-warn {
      border-color: rgba(200, 146, 59, 0.5);
      background: rgba(200, 146, 59, 0.1);
      display: flex;
      align-items: center;
      gap: 12rpx;
    }
  }
  &__lab-head {
    display: flex;
    align-items: center;
    gap: 12rpx;
  }
  &__lab-h {
    flex: 1;
    font-size: 27rpx;
    color: #8fe0cd;
  }
  &__lab-toggle {
    font-size: 24rpx;
    opacity: 0.8;
  }
  &__lab-body {
    margin-top: 12rpx;
    font-size: 27rpx;
    line-height: 1.7;
    color: $on-navy;
    white-space: pre-wrap;
  }
  &__lab-warn {
    flex: 1;
    font-size: 26rpx;
    line-height: 1.6;
    color: #e8c48a;
  }
  &__kv {
    display: flex;
    align-items: flex-start;
    gap: 16rpx;
    margin: 10rpx 0;
  }
  &__k {
    font-size: 26rpx;
    width: 72rpx;
    flex-shrink: 0;
    line-height: 48rpx;
  }
  &__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 12rpx;
  }
  &__tag {
    padding: 6rpx 20rpx;
    font-size: 26rpx;
    color: $on-navy;
    background: rgba(52, 80, 92, 0.5);
    border-radius: 999rpx;
    &--jade {
      background: rgba(95, 179, 161, 0.22);
      color: $jade;
    }
  }

  &__primary {
    font-size: 32rpx;
    color: $on-navy;
    margin-bottom: 8rpx;
  }
  &__bars {
    margin-top: 16rpx;
    display: flex;
    flex-direction: column;
    gap: 16rpx;
  }
  &__bar-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8rpx;
  }
  &__bar-name {
    font-size: 28rpx;
    color: $on-navy;
  }
  &__bar-score {
    font-size: 26rpx;
    color: $on-navy-2;
  }
  &__bar-track {
    height: 16rpx;
    border-radius: 8rpx;
    background: rgba(255, 255, 255, 0.08);
    overflow: hidden;
  }
  &__bar-fill {
    height: 100%;
    border-radius: 8rpx;
    background: $dai-qing;
    transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
    &.is-primary {
      background: linear-gradient(90deg, $gold-soft, $gold);
    }
  }

  &__evid {
    display: flex;
    flex-direction: column;
    gap: 14rpx;
  }
  &__evid-item {
    display: flex;
    gap: 14rpx;
    padding: 20rpx;
    border-radius: $radius-sm;
    background: rgba(200, 164, 92, 0.08);
    border: 1px solid rgba(200, 164, 92, 0.25);
    &--hover { background: rgba(200, 164, 92, 0.16); }
  }
  &__evid-text {
    font-size: 28rpx;
    line-height: 1.6;
    color: $on-navy;
  }
  &__evid-src {
    font-size: 24rpx;
    margin-top: 6rpx;
  }

  &__formula-name {
    font-size: 32rpx;
    font-weight: 700;
    margin-bottom: 16rpx;
  }
  &__jun {
    display: flex;
    flex-direction: column;
    gap: 16rpx;
  }
  &__jun-group {
    display: flex;
    gap: 16rpx;
  }
  &__jun-badge {
    width: 64rpx;
    height: 64rpx;
    border-radius: 14rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: $font-serif;
    font-size: 32rpx;
    font-weight: 700;
    color: $navy-2;
    flex-shrink: 0;
    &--jun { background: $gold; }
    &--chen { background: $dai-qing; color: $on-navy; }
    &--zuo { background: $jade; }
    &--shi { background: $jade; opacity: 0.8; }
    &--other { background: rgba(255, 255, 255, 0.2); color: $on-navy; }
  }
  &__jun-herbs {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8rpx;
    padding-top: 4rpx;
  }
  &__herb {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 12rpx;
  }
  &__herb-name {
    font-size: 30rpx;
    color: $on-navy;
    font-weight: 600;
  }
  &__herb-dose {
    font-size: 26rpx;
    color: $gold-soft;
  }
  &__herb-reason {
    font-size: 24rpx;
    width: 100%;
  }
  &__mod {
    margin-top: 16rpx;
    font-size: 28rpx;
    color: $on-navy-2;
  }

  /* 理论溯源（研究者专属）：金边卡，与经典印证呼应 */
  &__step--research {
    border-color: rgba(200, 164, 92, 0.3);
    background: rgba(200, 164, 92, 0.06);
  }
  &__cites {
    margin-top: 16rpx;
  }
  &__cites-label {
    font-size: 24rpx;
    margin-bottom: 10rpx;
  }
  &__cite {
    display: flex;
    flex-direction: column;
    gap: 4rpx;
    padding: 14rpx 18rpx;
    margin-bottom: 12rpx;
    border-radius: $radius-sm;
    background: rgba(200, 164, 92, 0.08);
    border: 1px solid rgba(200, 164, 92, 0.22);
  }
  &__cite-ref {
    font-size: 27rpx;
    font-weight: 600;
  }
  &__cite-point {
    font-size: 26rpx;
    line-height: 1.6;
    color: $on-navy;
  }

  &__care {
    display: flex;
    flex-direction: column;
    gap: 18rpx;
  }
  &__care-item {
    display: flex;
    gap: 16rpx;
  }
  &__care-seal {
    width: 52rpx;
    height: 52rpx;
    font-size: 28rpx;
    background: $dai-qing;
  }
  &__care-label {
    font-size: 24rpx;
    margin-bottom: 4rpx;
  }

  &__footer {
    display: flex;
    gap: 16rpx;
    margin: 16rpx 0 24rpx;
  }
  &__btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10rpx;
    min-height: 92rpx;
    border-radius: $radius-sm;
    font-size: 32rpx;
    &--primary {
      flex: 1;
      background: $cinnabar;
      color: $paper-card;
      font-weight: 600;
    }
    &--ghost {
      width: 200rpx;
      flex-shrink: 0;
      color: $on-navy;
      border: 1px solid rgba(255, 255, 255, 0.3);
    }
    &--hover { opacity: 0.85; }
  }
  &__disclaimer {
    font-size: 24rpx;
    line-height: 1.6;
    text-align: center;
    color: $on-navy-2;
    padding: 8rpx 24rpx 32rpx;
  }

  /* 切角色重新请求覆盖层 */
  &__switching {
    position: absolute;
    inset: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(15, 28, 36, 0.5);
    animation: rsSwitchIn 0.2s ease;
  }
  &__switching-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20rpx;
    padding: 40rpx 56rpx;
    border-radius: $radius;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.14);
  }
  &__switching-dots {
    display: flex;
    gap: 10rpx;
  }
  &__switching-dot {
    width: 14rpx;
    height: 14rpx;
    border-radius: 50%;
    background: $gold;
    animation: rsSwitchDot 1s ease-in-out infinite;
  }
  &__switching-txt {
    font-size: 28rpx;
    color: $on-navy;
  }
}

@keyframes rsSwitchIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes rsSwitchDot {
  0%, 100% { transform: translateY(0); opacity: 0.4; }
  50% { transform: translateY(-8rpx); opacity: 1; }
}

@keyframes stepIn {
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .rs__step { animation: none; opacity: 1; transform: none; }
  .rs__bar-fill { transition: none; }
}

/* 溯源 sheet */
.src {
  max-height: 72vh;
  display: flex;
  flex-direction: column;
  &__bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 28rpx 32rpx 16rpx;
  }
  &__title { font-size: 34rpx; font-weight: 700; color: $ink; }
  &__close { width: 56rpx; height: 56rpx; display: flex; align-items: center; justify-content: center; }
  &__scroll { flex: 1; min-height: 0; padding: 0 32rpx 32rpx; box-sizing: border-box; }
  &__meta { font-size: 24rpx; margin-bottom: 16rpx; }
  &__orig-label, &__plain-label { font-size: 24rpx; margin-bottom: 10rpx; }
  &__orig { font-size: 34rpx; line-height: 1.9; color: $cinnabar; }
  &__plain { font-size: 30rpx; line-height: 1.7; color: $ink; }
}

/* ===== 老年模式 ===== */
.gf-elder {
  /* 顶部角色 segmented（患/医/研）：交互元素同比增大 */
  .rs__roles { padding: 10rpx; }
  .rs__role { line-height: 96rpx; font-size: var(--gf-fs-base); border-radius: 16rpx; }
  /* 步骤锚点 chips：可点跳转，加大触控面 */
  .rs__anchors { margin-top: 20rpx; }
  .rs__anchors-row { gap: 16rpx; }
  .rs__anchor { padding: 18rpx 32rpx; font-size: var(--gf-fs-sm); }

  /* 横幅与主诉 */
  .rs__banner { font-size: var(--gf-fs-lg); margin-bottom: 12rpx; }
  .rs__chief { font-size: var(--gf-fs-base); line-height: var(--gf-lh); margin-bottom: 28rpx; }

  /* 步骤卡片：更宽松 */
  .rs__step { padding: 36rpx; margin-bottom: 32rpx; }
  .rs__step-head { gap: 20rpx; margin-bottom: 24rpx; }
  .rs__seal { width: 72rpx; height: 72rpx; font-size: var(--gf-fs-base); }
  /* 步骤标题 1.35× → 用 title token（已约 1.35×放大基线） */
  .rs__step-title { font-size: var(--gf-fs-title); }
  .rs__conf,
  .rs__role-tip { font-size: var(--gf-fs-sm); padding: 8rpx 24rpx; }
  .rs__lab-flag { font-size: var(--gf-fs-sm); padding: 8rpx 24rpx; gap: 10rpx; }

  /* 正文与键值 */
  .rs__para { font-size: var(--gf-fs-base); line-height: var(--gf-lh); margin-bottom: 10rpx; }
  .rs__kv { gap: 20rpx; margin: 16rpx 0; }
  .rs__k { font-size: var(--gf-fs-base); width: 100rpx; line-height: 64rpx; }
  .rs__tags { gap: 16rpx; }
  .rs__tag { padding: 12rpx 30rpx; font-size: var(--gf-fs-base); }

  /* 证型辨别 */
  .rs__primary { font-size: var(--gf-fs-lg); margin-bottom: 12rpx; }
  .rs__bars { margin-top: 24rpx; gap: 24rpx; }
  .rs__bar-label { margin-bottom: 12rpx; }
  .rs__bar-name { font-size: var(--gf-fs-base); }
  .rs__bar-score { font-size: var(--gf-fs-base); }
  .rs__bar-track { height: 22rpx; }

  /* 经典印证：可点条目 */
  .rs__evid { gap: 20rpx; }
  .rs__evid-item { gap: 20rpx; padding: 32rpx; min-height: 112rpx; }
  .rs__evid-text { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }
  .rs__evid-src { font-size: var(--gf-fs-sm); margin-top: 10rpx; }

  /* 方药配伍：君臣佐使更宽松（单列布局，徽标与药味垂直堆叠） */
  .rs__formula-name { font-size: var(--gf-fs-lg); margin-bottom: 24rpx; }
  .rs__jun { gap: 24rpx; }
  .rs__jun-group { flex-direction: column; gap: 16rpx; }
  .rs__jun-badge { width: 84rpx; height: 84rpx; font-size: var(--gf-fs-lg); }
  .rs__jun-herbs { gap: 14rpx; padding-top: 0; }
  .rs__herb { gap: 16rpx; }
  .rs__herb-name { font-size: var(--gf-fs-base); }
  .rs__herb-dose { font-size: var(--gf-fs-base); }
  .rs__herb-reason { font-size: var(--gf-fs-sm); line-height: var(--gf-lh); }
  .rs__mod { font-size: var(--gf-fs-base); }

  /* 调护医嘱 */
  .rs__care { gap: 26rpx; }
  .rs__care-item { gap: 20rpx; }
  .rs__care-seal { width: 68rpx; height: 68rpx; font-size: var(--gf-fs-base); }
  .rs__care-label { font-size: var(--gf-fs-sm); margin-bottom: 8rpx; }

  /* 底部按钮：交互元素 ≥112rpx */
  .rs__footer { gap: 20rpx; margin: 24rpx 0 32rpx; }
  .rs__btn { min-height: 116rpx; font-size: var(--gf-fs-lg); gap: 14rpx; }
  .rs__btn--ghost { width: 260rpx; }
  .rs__disclaimer { font-size: var(--gf-fs-sm); line-height: var(--gf-lh); padding: 12rpx 24rpx 40rpx; }

  /* 溯源 bottom sheet（宣纸原文/白话）：弹窗内联在根内，覆盖有效 */
  .src__bar { padding: 36rpx 32rpx 20rpx; }
  .src__title { font-size: var(--gf-fs-lg); }
  .src__close { width: 72rpx; height: 72rpx; }
  .src__meta { font-size: var(--gf-fs-sm); margin-bottom: 20rpx; }
  .src__orig-label,
  .src__plain-label { font-size: var(--gf-fs-sm); margin-bottom: 14rpx; }
  .src__orig { font-size: var(--gf-fs-title); line-height: var(--gf-lh); }
  .src__plain { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }
}
</style>
