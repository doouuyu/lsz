<script setup lang="ts">
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import type { Evidence, Herb, Role, SourceEntry, ViewModel } from "../../types";
import { useRoleStore } from "@/stores/role";

/**
 * 老年版 · 辨证结果长卷（dxe-result，藏青面）。
 * 契约同 dx-result（props vm/chief/sources/hasLab/roleSwitching；emit restart/export/role-change），
 * 角色逻辑完全复用同一套——role 取自全局 store，切换由父页 switchRole 重新请求 + 缓存，
 * 本组件只 emit role-change、读 roleSwitching 显示 loading、按 hasLab 显标识、按 research 渲染溯源节。
 * narration / openEvidence / 君臣佐使分组 / showDosage 逻辑与正常版一致。
 *
 * 重排（相对 dx-result 非放大，非缩放）：
 *  - 顶部移除横滚锚点 chips（老人易误触/价值低）；只留角色 segmented（加大触控）
 *    + 「朗读报告」gf-speaker 显著置顶（带文字标签、独占一行主控件）。
 *  - 8 步卡片单列、标题 title 大字、正文 base、印章序号放大、留白加大。
 *  - 证型 bar 加粗大字。
 *  - 方药君臣佐使纵向堆叠（徽标在上、药味在下逐行），剂量大字（患者视角隐藏剂量）。
 *  - 底部「导出脉案报告」独占整行大 CTA、「重新辨证」次级单独一行。
 *  - 溯源 sheet 大字；免责声明保留且 ≥ --gf-fs-sm（医疗合规红线）。
 *  class 全用独立 dxe-rs 命名空间，scoped。
 */
const props = defineProps<{
  vm: ViewModel;
  chief: string;
  sources: SourceEntry[];
  hasLab?: boolean;
  labFindings?: string; // 化验单要点（后端实读）→ 大字展开展示
  labUnreadable?: boolean; // 带了化验单但未识别 → 大字重拍提示
  roleSwitching?: boolean;
}>();

const emit = defineEmits<{
  (e: "restart"): void;
  (e: "export"): void;
  (e: "role-change", role: Role): void;
}>();

const roleStore = useRoleStore();
const { role } = storeToRefs(roleStore);
const showDosage = computed(() => role.value !== "patient");

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

/* 化验单要点展开态（默认展开） */
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
    source:
      ev.source ||
      [hit?.source?.book, hit?.source?.volume, hit?.source?.section].filter(Boolean).join("·"),
    original: hit?.original_text || ev.text || "",
    plain: hit?.plain_explanation || "",
  };
  srcShow.value = true;
}

/* 朗读叙述：与正常版一致 */
const narration = computed(() => {
  const vm = props.vm;
  const full = role.value !== "patient";
  const parts: string[] = [];

  if (props.chief?.trim()) parts.push(`主诉：${props.chief.trim()}。`);
  if (vm.summary?.trim()) parts.push(`症状归纳：${vm.summary.trim()}。`);

  const loc: string[] = [];
  const wei = (vm.location?.病位 || []).filter(Boolean);
  const xing = (vm.location?.病性 || []).filter(Boolean);
  if (wei.length) loc.push(`病位在${wei.join("、")}`);
  if (xing.length) loc.push(`病性属${xing.join("、")}`);
  if (vm.location?.气血津液?.trim()) loc.push(`气血津液方面，${vm.location.气血津液.trim()}`);
  if (loc.length) parts.push(`病位病性：${loc.join("，")}。`);

  const zheng: string[] = [];
  if (vm.primary?.trim()) zheng.push(`主证为${vm.primary.trim()}`);
  const conc = (vm.concurrent || []).filter(Boolean);
  if (conc.length) zheng.push(`兼有${conc.join("、")}`);
  if (zheng.length) parts.push(`证型辨别：${zheng.join("，")}。`);

  if (vm.treatment?.trim()) parts.push(`治法：${vm.treatment.trim()}。`);

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

  const careSeg: string[] = [];
  const c = vm.care;
  if (c?.contraindication?.trim()) careSeg.push(`用药禁忌，${c.contraindication.trim()}`);
  if (c?.diet?.trim()) careSeg.push(`食疗建议，${c.diet.trim()}`);
  if (c?.lifestyle?.trim()) careSeg.push(`起居调护，${c.lifestyle.trim()}`);
  if (c?.exercise?.trim()) careSeg.push(`简易功法，${c.exercise.trim()}`);
  if (careSeg.length) parts.push(`调护医嘱：${careSeg.join("；")}。`);

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
  <view class="dxe dxe-rs gf-navy">
    <!-- 顶部：角色 segmented（加大）+ 朗读报告显著置顶；无横滚锚点 -->
    <view class="dxe-rs__top">
      <view class="dxe-rs__roles">
        <view class="dxe-rs__role active">
          报告视角：{{ role === "patient" ? "患者" : role === "doctor" ? "医师" : "研究者" }}（已锁定）
        </view>
      </view>
      <view class="dxe-rs__speak-row">
        <gf-speaker
          tone="navy"
          :text="narration"
          label="朗读报告"
          :size="48"
          class="dxe-rs__speak"
        />
      </view>
    </view>

    <scroll-view scroll-y class="dxe-rs__scroll">
      <view class="dxe-rs__banner">
        <gf-icon name="check" :size="44" color="#5FB3A1" />
        <text>四诊已明 · 辨证如下</text>
      </view>
      <view class="dxe-rs__chief gf-on-navy-2">主诉：{{ chief }}</view>

      <!-- ① 症状归纳 -->
      <view class="dxe-rs__step">
        <view class="dxe-rs__step-head">
          <view class="dxe-rs__seal gf-seal gf-serif">1</view>
          <view class="dxe-rs__step-title gf-serif">症状归纳</view>
          <view v-if="hasLab" class="dxe-rs__lab-flag">
            <gf-icon name="file" :size="28" color="#5FB3A1" /><text>已纳入医疗附件</text>
          </view>
        </view>
        <view class="dxe-rs__para">{{ vm.summary || "—" }}</view>
        <!-- 化验单要点：大字展开，让老人也能看到「确实读了化验单」 -->
        <view v-if="labFindings" class="dxe-rs__lab">
          <view class="dxe-rs__lab-head" @tap="labOpen = !labOpen">
            <gf-icon name="file" :size="36" color="#5FB3A1" />
            <text class="dxe-rs__lab-h gf-serif">化验单要点（已读取并纳入）</text>
            <text class="dxe-rs__lab-toggle gf-on-navy-2">{{ labOpen ? "收起" : "展开" }}</text>
          </view>
          <view v-if="labOpen" class="dxe-rs__lab-body">{{ labFindings }}</view>
        </view>
        <view v-else-if="labUnreadable" class="dxe-rs__lab is-warn">
          <gf-icon name="file" :size="36" color="#C8923B" />
          <text class="dxe-rs__lab-warn">化验单没能看清，本次没算进去。请重拍一张更清楚、光线足的照片。</text>
        </view>
      </view>

      <!-- ② 病位病性 -->
      <view class="dxe-rs__step">
        <view class="dxe-rs__step-head">
          <view class="dxe-rs__seal gf-seal gf-serif">2</view>
          <view class="dxe-rs__step-title gf-serif">病位病性</view>
        </view>
        <view class="dxe-rs__kv">
          <text class="dxe-rs__k gf-on-navy-2">病位</text>
          <view class="dxe-rs__tags"><text v-for="(t, i) in vm.location.病位" :key="i" class="dxe-rs__tag">{{ t }}</text></view>
        </view>
        <view class="dxe-rs__kv">
          <text class="dxe-rs__k gf-on-navy-2">病性</text>
          <view class="dxe-rs__tags"><text v-for="(t, i) in vm.location.病性" :key="i" class="dxe-rs__tag dxe-rs__tag--jade">{{ t }}</text></view>
        </view>
        <view v-if="vm.location.气血津液" class="dxe-rs__para">气血津液：{{ vm.location.气血津液 }}</view>
      </view>

      <!-- ③ 证型辨别 -->
      <view class="dxe-rs__step">
        <view class="dxe-rs__step-head">
          <view class="dxe-rs__seal gf-seal gf-serif">3</view>
          <view class="dxe-rs__step-title gf-serif">证型辨别</view>
        </view>
        <view class="dxe-rs__conf" :class="confidence.cls">把握 {{ confidence.label }} · {{ vm.confidence }}%</view>
        <view class="dxe-rs__primary">主证：<text class="gf-gold">{{ vm.primary }}</text></view>
        <view v-if="vm.concurrent.length" class="dxe-rs__kv">
          <text class="dxe-rs__k gf-on-navy-2">兼证</text>
          <view class="dxe-rs__tags"><text v-for="(t, i) in vm.concurrent" :key="i" class="dxe-rs__tag">{{ t }}</text></view>
        </view>
        <view class="dxe-rs__bars">
          <view v-for="(c, i) in vm.candidates" :key="i" class="dxe-rs__bar">
            <view class="dxe-rs__bar-label">
              <text class="dxe-rs__bar-name">{{ c.name }}</text>
              <text class="dxe-rs__bar-score gf-tnum">{{ c.score }}%</text>
            </view>
            <view class="dxe-rs__bar-track">
              <view class="dxe-rs__bar-fill" :class="{ 'is-primary': i === 0 }" :style="{ width: c.score + '%' }" />
            </view>
          </view>
        </view>
      </view>

      <!-- ④ 经典印证 -->
      <view class="dxe-rs__step">
        <view class="dxe-rs__step-head">
          <view class="dxe-rs__seal gf-seal gf-serif">4</view>
          <view class="dxe-rs__step-title gf-serif">经典印证</view>
        </view>
        <view v-if="vm.evidence.length" class="dxe-rs__evid">
          <view
            v-for="(ev, i) in vm.evidence"
            :key="i"
            class="dxe-rs__evid-item"
            hover-class="dxe-rs__evid-item--hover"
            @tap="openEvidence(ev)"
          >
            <gf-icon name="book" :size="36" color="#C8A45C" />
            <view class="dxe-rs__evid-body">
              <view class="dxe-rs__evid-text">{{ ev.text }}</view>
              <view class="dxe-rs__evid-src gf-on-navy-2">{{ ev.source }}</view>
            </view>
          </view>
        </view>
        <view v-else class="dxe-rs__para gf-on-navy-2">—</view>
      </view>

      <!-- ⑤ 治法确立 -->
      <view class="dxe-rs__step">
        <view class="dxe-rs__step-head">
          <view class="dxe-rs__seal gf-seal gf-serif">5</view>
          <view class="dxe-rs__step-title gf-serif">治法确立</view>
        </view>
        <view class="dxe-rs__para">{{ vm.treatment || "—" }}</view>
      </view>

      <!-- ⑥ 方药配伍 -->
      <view class="dxe-rs__step">
        <view class="dxe-rs__step-head">
          <view class="dxe-rs__seal gf-seal gf-serif">6</view>
          <view class="dxe-rs__step-title gf-serif">方药配伍</view>
        </view>
        <view v-if="!showDosage" class="dxe-rs__role-tip gf-on-navy-2">患者视角已隐藏剂量</view>
        <view v-if="vm.formula.name" class="dxe-rs__formula-name gf-gold gf-serif">{{ vm.formula.name }}</view>
        <view class="dxe-rs__jun">
          <view v-for="g in groups" :key="g.key" class="dxe-rs__jun-group">
            <view class="dxe-rs__jun-badge" :class="'dxe-rs__jun-badge--' + g.cls">{{ g.key }}</view>
            <view class="dxe-rs__jun-herbs">
              <view v-for="(h, i) in g.herbs" :key="i" class="dxe-rs__herb">
                <text class="dxe-rs__herb-name">{{ h.herb }}</text>
                <text v-if="showDosage && h.dosage" class="dxe-rs__herb-dose gf-tnum">{{ h.dosage }}</text>
                <text v-if="showDosage && h.reason" class="dxe-rs__herb-reason gf-on-navy-2">{{ h.reason }}</text>
              </view>
            </view>
          </view>
          <view v-if="otherHerbs.length" class="dxe-rs__jun-group">
            <view class="dxe-rs__jun-badge dxe-rs__jun-badge--other">药</view>
            <view class="dxe-rs__jun-herbs">
              <view v-for="(h, i) in otherHerbs" :key="i" class="dxe-rs__herb">
                <text class="dxe-rs__herb-name">{{ h.herb }}</text>
                <text v-if="showDosage && h.dosage" class="dxe-rs__herb-dose gf-tnum">{{ h.dosage }}</text>
              </view>
            </view>
          </view>
        </view>
        <view v-if="vm.formula.modification" class="dxe-rs__para dxe-rs__mod">随症加减：{{ vm.formula.modification }}</view>
      </view>

      <!-- ⑦ 调护医嘱 -->
      <view class="dxe-rs__step">
        <view class="dxe-rs__step-head">
          <view class="dxe-rs__seal gf-seal gf-serif">7</view>
          <view class="dxe-rs__step-title gf-serif">调护医嘱</view>
        </view>
        <view class="dxe-rs__care">
          <view v-for="(c, i) in careItems" :key="i" class="dxe-rs__care-item">
            <view class="dxe-rs__care-seal gf-seal gf-serif">{{ c.seal }}</view>
            <view class="dxe-rs__care-body">
              <view class="dxe-rs__care-label gf-on-navy-2">{{ c.label }}</view>
              <view class="dxe-rs__para">{{ c.text }}</view>
            </view>
          </view>
        </view>
      </view>

      <!-- ⑧ 理论溯源（研究者专属） -->
      <view v-if="vm.research" class="dxe-rs__step dxe-rs__step--research">
        <view class="dxe-rs__step-head">
          <view class="dxe-rs__seal gf-seal gf-serif">研</view>
          <view class="dxe-rs__step-title gf-serif">理论溯源</view>
        </view>
        <view v-if="vm.research.theoryOrigin" class="dxe-rs__para">{{ vm.research.theoryOrigin }}</view>
        <view v-if="vm.research.citations.length" class="dxe-rs__cites">
          <view class="dxe-rs__cites-label gf-on-navy-2">文献引证</view>
          <view v-for="(c, i) in vm.research.citations" :key="i" class="dxe-rs__cite">
            <text class="dxe-rs__cite-ref gf-gold">{{ c.ref }}</text>
            <text v-if="c.point" class="dxe-rs__cite-point">{{ c.point }}</text>
          </view>
        </view>
        <view v-if="vm.research.schools" class="dxe-rs__cites">
          <view class="dxe-rs__cites-label gf-on-navy-2">学术流派</view>
          <view class="dxe-rs__para">{{ vm.research.schools }}</view>
        </view>
      </view>

      <!-- footer：导出独占整行大 CTA，重辨次级单独一行 -->
      <view class="dxe-rs__footer">
        <view class="dxe-rs__cta" hover-class="dxe-rs__cta--hover" @tap="emit('export')">
          <gf-icon name="report" :size="44" color="#FBF7EE" /><text>导出脉案报告</text>
        </view>
        <view class="dxe-rs__restart" hover-class="dxe-rs__restart--hover" @tap="emit('restart')">重新辨证</view>
      </view>
      <view class="dxe-rs__disclaimer">{{ vm.disclaimer }}</view>
    </scroll-view>

    <!-- 溯源原文 sheet（大字） -->
    <wd-popup
      v-model="srcShow"
      position="bottom"
      :safe-area-inset-bottom="true"
      custom-style="border-radius:28rpx 28rpx 0 0;background:#F3ECDD;"
    >
      <view class="dxe-src" @touchmove.stop>
        <view class="dxe-src__bar">
          <view class="dxe-src__title gf-serif">{{ activeSrc?.title }}</view>
          <view class="dxe-src__close" @tap="srcShow = false"><gf-icon name="close" :size="44" color="#5C5345" /></view>
        </view>
        <scroll-view scroll-y class="dxe-src__scroll">
          <view v-if="activeSrc?.source" class="dxe-src__meta gf-ink-3">{{ activeSrc.source }}</view>
          <view class="dxe-src__orig-label gf-ink-3">原文</view>
          <view class="dxe-src__orig gf-serif">{{ activeSrc?.original || "—" }}</view>
          <template v-if="activeSrc?.plain">
            <view class="dxe-src__divider" />
            <view class="dxe-src__plain-label gf-ink-3">白话</view>
            <view class="dxe-src__plain">{{ activeSrc.plain }}</view>
          </template>
        </scroll-view>
      </view>
    </wd-popup>

    <!-- 切角色重新请求覆盖层 -->
    <view v-if="roleSwitching" class="dxe-rs__switching" @touchmove.stop.prevent>
      <view class="dxe-rs__switching-card">
        <view class="dxe-rs__switching-dots">
          <view
            v-for="i in 3"
            :key="i"
            class="dxe-rs__switching-dot"
            :style="{ animationDelay: i * 0.16 + 's' }"
          />
        </view>
        <text class="dxe-rs__switching-txt">正在为{{
          role === "patient" ? "患者" : role === "doctor" ? "医师" : "研究者"
        }}重新生成…</text>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.dxe-rs {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-radius: 0;

  &__top {
    padding: 20rpx var(--dxe-pad) 16rpx;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  &__roles {
    display: flex;
    background: rgba(255, 255, 255, 0.06);
    border-radius: var(--dxe-radius-sm);
    padding: 10rpx;
    box-sizing: border-box;
    &.is-switching {
      opacity: 0.55;
      pointer-events: none;
    }
  }
  &__role {
    flex: 1;
    text-align: center;
    line-height: 96rpx;
    font-size: var(--gf-fs-base);
    color: $on-navy-2;
    border-radius: 14rpx;
    &.active {
      background: $cinnabar;
      color: $paper-card;
      font-weight: 600;
    }
  }
  /* 朗读报告：独占一行显著主控件 */
  &__speak-row {
    display: flex;
    margin-top: 16rpx;
  }
  &__speak {
    flex: 1;
    justify-content: center;
    min-height: var(--dxe-tap-h);
  }

  &__scroll {
    flex: 1;
    min-height: 0;
    padding: 24rpx var(--dxe-pad) env(safe-area-inset-bottom);
    box-sizing: border-box;
  }
  &__banner {
    display: flex;
    align-items: center;
    gap: 14rpx;
    font-size: var(--gf-fs-lg);
    color: $jade;
    font-family: $font-serif;
    margin-bottom: 12rpx;
  }
  &__chief {
    font-size: var(--gf-fs-base);
    line-height: var(--gf-lh);
    margin-bottom: 28rpx;
  }

  &__step {
    padding: 36rpx;
    margin-bottom: 28rpx;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: var(--dxe-radius);
  }
  &__step-head {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 20rpx;
    margin-bottom: 24rpx;
  }
  &__seal {
    width: 76rpx;
    height: 76rpx;
    font-size: var(--gf-fs-base);
  }
  &__step-title {
    font-size: var(--gf-fs-title);
    font-weight: 700;
    color: $on-navy;
  }
  &__lab-flag {
    display: inline-flex;
    align-items: center;
    gap: 10rpx;
    font-size: var(--gf-fs-sm);
    padding: 8rpx 24rpx;
    border-radius: 999rpx;
    color: $jade;
    background: rgba(95, 179, 161, 0.14);
    border: 1px solid rgba(95, 179, 161, 0.4);
  }
  &__conf {
    display: inline-flex;
    align-self: flex-start;
    font-size: var(--gf-fs-sm);
    padding: 8rpx 24rpx;
    margin-bottom: 16rpx;
    border-radius: 999rpx;
    border: 1px solid;
    &.high { color: $jade; border-color: $jade; }
    &.mid { color: $gold; border-color: $gold; }
    &.low { color: $on-navy-2; border-color: rgba(255, 255, 255, 0.3); }
  }
  &__role-tip {
    display: inline-flex;
    align-self: flex-start;
    font-size: var(--gf-fs-sm);
    padding: 8rpx 24rpx;
    margin-bottom: 16rpx;
    border-radius: 999rpx;
    border: 1px solid rgba(255, 255, 255, 0.2);
  }

  &__para {
    font-size: var(--gf-fs-base);
    line-height: var(--gf-lh);
    color: $on-navy;
    margin-bottom: 10rpx;
  }
  /* 化验单要点卡（老年大字） */
  &__lab {
    margin-top: 20rpx;
    padding: 24rpx 28rpx;
    border: 2rpx solid rgba(95, 179, 161, 0.5);
    border-radius: 18rpx;
    background: rgba(95, 179, 161, 0.1);
    &.is-warn {
      border-color: rgba(200, 146, 59, 0.55);
      background: rgba(200, 146, 59, 0.12);
      display: flex;
      align-items: center;
      gap: 18rpx;
    }
  }
  &__lab-head {
    display: flex;
    align-items: center;
    gap: 18rpx;
  }
  &__lab-h {
    flex: 1;
    font-size: var(--gf-fs-base);
    color: #8fe0cd;
  }
  &__lab-toggle {
    font-size: var(--gf-fs-sm);
  }
  &__lab-body {
    margin-top: 16rpx;
    font-size: var(--gf-fs-base);
    line-height: var(--gf-lh);
    color: $on-navy;
    white-space: pre-wrap;
  }
  &__lab-warn {
    flex: 1;
    font-size: var(--gf-fs-base);
    line-height: var(--gf-lh);
    color: #e8c48a;
  }
  &__kv {
    display: flex;
    align-items: flex-start;
    gap: 20rpx;
    margin: 16rpx 0;
  }
  &__k {
    font-size: var(--gf-fs-base);
    width: 100rpx;
    flex-shrink: 0;
    line-height: 64rpx;
  }
  &__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 16rpx;
  }
  &__tag {
    padding: 12rpx 30rpx;
    font-size: var(--gf-fs-base);
    color: $on-navy;
    background: rgba(52, 80, 92, 0.5);
    border-radius: 999rpx;
    &--jade {
      background: rgba(95, 179, 161, 0.22);
      color: $jade;
    }
  }

  &__primary {
    font-size: var(--gf-fs-lg);
    color: $on-navy;
    margin-bottom: 12rpx;
  }
  &__bars {
    margin-top: 24rpx;
    display: flex;
    flex-direction: column;
    gap: 24rpx;
  }
  &__bar-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 12rpx;
  }
  &__bar-name {
    font-size: var(--gf-fs-base);
    color: $on-navy;
  }
  &__bar-score {
    font-size: var(--gf-fs-base);
    color: $on-navy-2;
  }
  &__bar-track {
    height: 24rpx;
    border-radius: 12rpx;
    background: rgba(255, 255, 255, 0.08);
    overflow: hidden;
  }
  &__bar-fill {
    height: 100%;
    border-radius: 12rpx;
    background: $dai-qing;
    transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
    &.is-primary {
      background: linear-gradient(90deg, $gold-soft, $gold);
    }
  }

  &__evid {
    display: flex;
    flex-direction: column;
    gap: 20rpx;
  }
  &__evid-item {
    display: flex;
    gap: 20rpx;
    padding: 32rpx;
    border-radius: var(--dxe-radius-sm);
    background: rgba(200, 164, 92, 0.08);
    border: 1px solid rgba(200, 164, 92, 0.25);
    &--hover { background: rgba(200, 164, 92, 0.16); }
  }
  &__evid-text {
    font-size: var(--gf-fs-base);
    line-height: var(--gf-lh);
    color: $on-navy;
  }
  &__evid-src {
    font-size: var(--gf-fs-sm);
    margin-top: 10rpx;
  }

  &__formula-name {
    font-size: var(--gf-fs-lg);
    font-weight: 700;
    margin-bottom: 24rpx;
  }
  /* 君臣佐使纵向堆叠：徽标在上、药味在下逐行 */
  &__jun {
    display: flex;
    flex-direction: column;
    gap: 28rpx;
  }
  &__jun-group {
    display: flex;
    flex-direction: column;
    gap: 16rpx;
  }
  &__jun-badge {
    width: 88rpx;
    height: 88rpx;
    border-radius: 18rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: $font-serif;
    font-size: var(--gf-fs-lg);
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
    display: flex;
    flex-direction: column;
    gap: 16rpx;
  }
  &__herb {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 16rpx;
  }
  &__herb-name {
    font-size: var(--gf-fs-base);
    color: $on-navy;
    font-weight: 600;
  }
  &__herb-dose {
    font-size: var(--gf-fs-base);
    color: $gold-soft;
  }
  &__herb-reason {
    font-size: var(--gf-fs-sm);
    line-height: var(--gf-lh);
    width: 100%;
  }
  &__mod {
    margin-top: 20rpx;
    font-size: var(--gf-fs-base);
    color: $on-navy-2;
  }

  &__step--research {
    border-color: rgba(200, 164, 92, 0.3);
    background: rgba(200, 164, 92, 0.06);
  }
  &__cites {
    margin-top: 20rpx;
  }
  &__cites-label {
    font-size: var(--gf-fs-sm);
    margin-bottom: 12rpx;
  }
  &__cite {
    display: flex;
    flex-direction: column;
    gap: 8rpx;
    padding: 22rpx 24rpx;
    margin-bottom: 16rpx;
    border-radius: var(--dxe-radius-sm);
    background: rgba(200, 164, 92, 0.08);
    border: 1px solid rgba(200, 164, 92, 0.22);
  }
  &__cite-ref {
    font-size: var(--gf-fs-base);
    font-weight: 600;
  }
  &__cite-point {
    font-size: var(--gf-fs-sm);
    line-height: var(--gf-lh);
    color: $on-navy;
  }

  &__care {
    display: flex;
    flex-direction: column;
    gap: 26rpx;
  }
  &__care-item {
    display: flex;
    gap: 20rpx;
  }
  &__care-seal {
    width: 68rpx;
    height: 68rpx;
    font-size: var(--gf-fs-base);
    background: $dai-qing;
  }
  &__care-label {
    font-size: var(--gf-fs-sm);
    margin-bottom: 8rpx;
  }

  /* footer */
  &__footer {
    display: flex;
    flex-direction: column;
    gap: 20rpx;
    margin: 24rpx 0 28rpx;
  }
  &__cta {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14rpx;
    width: 100%;
    min-height: var(--dxe-cta-h);
    border-radius: var(--dxe-radius);
    background: $cinnabar;
    color: $paper-card;
    font-size: var(--gf-fs-lg);
    font-weight: 600;
    box-sizing: border-box;
    &--hover { background: $cinnabar-soft; }
  }
  &__restart {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: var(--dxe-tap-h);
    border-radius: var(--dxe-radius-sm);
    font-size: var(--gf-fs-base);
    color: $on-navy;
    border: 2rpx solid rgba(255, 255, 255, 0.3);
    box-sizing: border-box;
    &--hover { opacity: 0.85; }
  }
  &__disclaimer {
    font-size: var(--gf-fs-sm);
    line-height: var(--gf-lh);
    text-align: center;
    color: $on-navy-2;
    padding: 12rpx 24rpx 40rpx;
  }

  /* 切角色覆盖层 */
  &__switching {
    position: absolute;
    inset: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(15, 28, 36, 0.5);
    animation: dxeRsSwitchIn 0.2s ease;
  }
  &__switching-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24rpx;
    padding: 48rpx 64rpx;
    border-radius: var(--dxe-radius);
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.14);
  }
  &__switching-dots {
    display: flex;
    gap: 14rpx;
  }
  &__switching-dot {
    width: 18rpx;
    height: 18rpx;
    border-radius: 50%;
    background: $gold;
    animation: dxeRsSwitchDot 1s ease-in-out infinite;
  }
  &__switching-txt {
    font-size: var(--gf-fs-base);
    color: $on-navy;
  }
}

@keyframes dxeRsSwitchIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes dxeRsSwitchDot {
  0%, 100% { transform: translateY(0); opacity: 0.4; }
  50% { transform: translateY(-8rpx); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .dxe-rs__bar-fill { transition: none; }
}

/* 溯源 sheet（大字） */
.dxe-src {
  max-height: 78vh;
  display: flex;
  flex-direction: column;
  &__bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 36rpx 32rpx 20rpx;
  }
  &__title { font-size: var(--gf-fs-lg); font-weight: 700; color: $ink; }
  &__close { width: 80rpx; height: 80rpx; display: flex; align-items: center; justify-content: center; }
  &__scroll { flex: 1; min-height: 0; padding: 0 32rpx 32rpx; box-sizing: border-box; }
  &__meta { font-size: var(--gf-fs-sm); margin-bottom: 20rpx; }
  &__orig-label, &__plain-label { font-size: var(--gf-fs-sm); margin-bottom: 14rpx; }
  &__orig { font-size: var(--gf-fs-title); line-height: var(--gf-lh); color: $cinnabar; }
  &__divider {
    height: 2rpx;
    background: linear-gradient(90deg, transparent, $gold 18%, $gold 82%, transparent);
    opacity: 0.7;
    margin: 32rpx 0;
  }
  &__plain { font-size: var(--gf-fs-base); line-height: var(--gf-lh); color: $ink; }
}
</style>
