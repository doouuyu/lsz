<script setup lang="ts">
import { ref, computed } from "vue";
import { COMMON_CHIEFS } from "../../mock";
import { useVoiceInput } from "@/composables/useVoiceInput";

/**
 * 老年版 · 录入卡（dxe-intake，宣纸面全屏）。
 * 契约同 dx-intake（props tongueStatus/tongueImg/tongueDesc/tongueHint/labFiles；
 * emit submit/tongue-confirm/tongue-remove/lab-add/lab-remove/lab-retry），逻辑零重复。
 *
 * 重排（相对 dx-intake 非放大，非缩放）：
 *  - 取消「一行四挤」：底部仅留「开始辨证」独占整行大 CTA（每屏一个主 CTA）。
 *  - 「按住说语音 / 拍舌象 / 传化验单」从 CTA 行拆出，改为题干下方一排大图标+大文字方块
 *    （语音排首位、提升为主路径），触控 ≥ 160rpx。
 *  - 常见主诉 chips 改双列大号点选块（非横排小 chip）。
 *  - 舌象 / 化验单卡单列、缩略图加大、状态大字、重拍/删除/重传为大可点项。
 *  - 舌象全屏取景层按钮放大、提示大字。
 *  class 全用独立 dxe-it 命名空间，scoped。
 */
interface LabFile {
  localPath: string;
  isPdf: boolean;
  status: "uploading" | "done" | "failed";
  labId?: string;
}
const props = withDefaults(
  defineProps<{
    tongueStatus: "idle" | "analyzing" | "done" | "degraded" | "retake";
    tongueImg: string;
    tongueDesc: string;
    tongueHint: string;
    labFiles?: LabFile[];
  }>(),
  { labFiles: () => [] }
);
const emit = defineEmits<{
  (e: "submit", chief: string): void;
  (e: "tongue-confirm", filePath: string): void;
  (e: "tongue-remove"): void;
  (e: "lab-add", items: { path: string; isPdf: boolean }[]): void;
  (e: "lab-remove", index: number): void;
  (e: "lab-retry", index: number): void;
}>();

const chief = ref("");
const focused = ref(false);
const canSubmit = computed(() => chief.value.trim().length > 0);

/* —— 舌象拍照取景 —— */
const previewImg = ref("");
const showTonguePreview = ref(false);

function chooseTongue() {
  uni.chooseMedia({
    count: 1,
    mediaType: ["image"],
    sourceType: ["camera", "album"],
    sizeType: ["compressed"],
    camera: "back",
    success: (res: any) => {
      const f = res?.tempFiles?.[0];
      if (f?.tempFilePath) {
        previewImg.value = f.tempFilePath;
        showTonguePreview.value = true;
      }
    },
    fail: () => {},
  });
}
function retakeTongue() {
  showTonguePreview.value = false;
  previewImg.value = "";
  chooseTongue();
}
function confirmTongue() {
  if (!previewImg.value) return;
  const path = previewImg.value;
  emit("tongue-confirm", path);
  showTonguePreview.value = false;
  previewImg.value = "";
  uni.vibrateShort?.({ type: "light" } as any);
}
function removeTongue() {
  emit("tongue-remove");
}

function appendChief(text: string) {
  const cur = chief.value.trim();
  if (!cur) chief.value = text;
  else if (cur.includes(text)) return;
  else chief.value = cur + (/[。！？；，,.!?;]$/.test(cur) ? "" : "，") + text;
}

function onSubmit() {
  if (!canSubmit.value) {
    uni.showToast({ title: "请先描述主要不适", icon: "none" });
    return;
  }
  emit("submit", chief.value.trim());
}

/* —— 长按语音 —— */
const {
  supported: voiceSupported,
  recording,
  processing,
  cancelArmed,
  seconds,
  liveText,
  onPressStart,
  onPressMove,
  onPressEnd,
} = useVoiceInput({ onResult: appendChief });

/* —— 统一附件入口：后端自动识别舌象、报告、处方和病历 —— */
function chooseLab() {
  const itemList = ["拍照或从相册选择"];
  // #ifdef MP-WEIXIN
  itemList.push("选择聊天文件（PDF）");
  // #endif
  uni.showActionSheet({
    itemList,
    success: ({ tapIndex }) => {
      if (tapIndex === 0) chooseLabImages();
      else if (tapIndex === 1) chooseLabPdf();
    },
    fail: () => {},
  });
}
function chooseLabImages() {
  uni.chooseMedia({
    count: Math.max(1, 5 - props.labFiles.length),
    mediaType: ["image"],
    sourceType: ["camera", "album"],
    sizeType: ["compressed"],
    success: (res: any) => {
      const files = (res?.tempFiles || [])
        .map((f: any) => f?.tempFilePath)
        .filter(Boolean)
        .map((path: string) => ({ path, isPdf: false }));
      if (files.length) emit("lab-add", files);
    },
    fail: () => {},
  });
}
function chooseLabPdf() {
  // #ifdef MP-WEIXIN
  uni.chooseMessageFile({
    count: 9,
    type: "file",
    extension: ["pdf"],
    success: (res: any) => {
      const files = (res?.tempFiles || [])
        .map((f: any) => f?.path)
        .filter(Boolean)
        .map((path: string) => ({ path, isPdf: true }));
      if (files.length) emit("lab-add", files);
    },
    fail: () => {},
  });
  // #endif
}
</script>

<template>
  <view class="dxe dxe-it">
    <scroll-view scroll-y class="dxe-it__scroll">
      <!-- 引导 -->
      <view class="dxe-it__lead">
        <view class="dxe-it__seal gf-seal gf-serif">问</view>
        <view class="dxe-it__lead-text">
          <view class="dxe-it__title gf-serif">请描述您的主要不适</view>
          <view class="dxe-it__sub gf-ink-3">说得越具体，辨证越准</view>
        </view>
      </view>

      <!-- 主诉输入 -->
      <view class="dxe-it__field gf-card" :class="{ 'is-focus': focused }">
        <textarea
          v-model="chief"
          class="dxe-it__textarea"
          :maxlength="-1"
          :auto-height="true"
          :adjust-position="true"
          :cursor-spacing="24"
          :show-confirm-bar="false"
          placeholder="如：失眠三个月，入睡困难，夜里多梦易醒…"
          placeholder-class="dxe-it__ph"
          @focus="focused = true"
          @blur="focused = false"
        />
      </view>

      <!-- 输入方式：大图标+大文字横排（语音首位、主路径） -->
      <view class="dxe-it__tools">
        <view
          class="dxe-it__tool"
          :class="{ 'is-recording': recording, 'is-off': !voiceSupported }"
          @touchstart.stop.prevent="onPressStart"
          @touchmove.stop.prevent="onPressMove"
          @touchend.stop.prevent="onPressEnd"
          @touchcancel.stop.prevent="onPressEnd"
        >
          <gf-icon name="mic" :size="56" :color="recording ? '#FBF7EE' : '#9A2D2D'" />
          <text class="dxe-it__tool-text">按住说话</text>
        </view>
        <view class="dxe-it__tool" :class="{ 'is-done': labFiles.length }" @tap="chooseLab">
          <gf-icon name="file" :size="56" :color="labFiles.length ? '#9A2D2D' : '#5C5345'" />
          <text class="dxe-it__tool-text">{{ labFiles.length ? `已选 ${labFiles.length} 个附件` : "上传医疗附件" }}</text>
        </view>
      </view>

      <!-- 常见主诉：双列大号点选块 -->
      <view class="dxe-it__chips-label gf-ink-3">常见主诉 · 点选快速填入</view>
      <view class="dxe-it__chips">
        <view
          v-for="c in COMMON_CHIEFS"
          :key="c"
          class="dxe-it__chip"
          hover-class="dxe-it__chip--hover"
          :hover-stay-time="60"
          @tap="appendChief(c)"
        >{{ c }}</view>
      </view>

      <!-- 舌象缩略卡：单列大缩略图大状态字 -->
      <view v-if="tongueImg" class="dxe-it__tongue-card gf-card" :class="`is-${tongueStatus}`">
        <view class="dxe-it__tongue-figure">
          <image
            class="dxe-it__tongue-thumb"
            :class="{ 'is-analyzing': tongueStatus === 'analyzing' }"
            :src="tongueImg"
            mode="aspectFill"
          />
          <view v-if="tongueStatus === 'analyzing'" class="dxe-it__tongue-scan" />
          <view
            class="dxe-it__tongue-stamp gf-serif"
            :class="{
              'is-pending': tongueStatus === 'analyzing',
              'is-set': tongueStatus === 'done',
            }"
          >舌</view>
        </view>
        <view class="dxe-it__tongue-meta">
          <view v-if="tongueStatus === 'analyzing'" class="dxe-it__tongue-status gf-serif">
            <text>舌象识别中</text>
          </view>
          <view v-else-if="tongueStatus === 'done'" class="dxe-it__tongue-ok gf-serif">
            <gf-icon name="check" :size="40" color="#5FB3A1" />
            <text>舌象已识别</text>
          </view>
          <view v-else-if="tongueStatus === 'retake'" class="dxe-it__tongue-warn gf-serif">
            <text>建议重拍</text>
          </view>
          <view v-else class="dxe-it__tongue-ok gf-serif">
            <gf-icon name="check" :size="40" color="#A99" />
            <text>舌象照片已保留</text>
          </view>

          <view v-if="tongueStatus === 'done' && tongueDesc" class="dxe-it__tongue-desc gf-ink-2">
            {{ tongueDesc }}
          </view>
          <view v-else-if="tongueStatus === 'analyzing'" class="dxe-it__tongue-desc gf-ink-3">
            识别在后台进行，您可以继续往下填
          </view>
          <view
            v-else-if="(tongueStatus === 'retake' || tongueStatus === 'degraded') && tongueHint"
            class="dxe-it__tongue-desc gf-ink-3"
          >
            {{ tongueHint }}
          </view>

          <view class="dxe-it__tongue-ops">
            <view class="dxe-it__tongue-op" hover-class="dxe-it__tongue-op--hover" @tap="chooseTongue">重拍</view>
            <view class="dxe-it__tongue-op dxe-it__tongue-op--del" hover-class="dxe-it__tongue-op--hover" @tap="removeTongue">删除</view>
          </view>
        </view>
      </view>

      <!-- 化验单卡：单列大缩略图 -->
      <view v-if="labFiles.length" class="dxe-it__lab-card gf-card">
        <view class="dxe-it__lab-title gf-serif">
          医疗附件 · {{ labFiles.length }} 份
          <text class="dxe-it__lab-title-sub gf-ink-3">（自动识别类型，仅作问诊参考）</text>
        </view>
        <view class="dxe-it__lab-list">
          <view v-for="(f, i) in labFiles" :key="i" class="dxe-it__lab-item">
            <view class="dxe-it__lab-figure">
              <image
                v-if="!f.isPdf"
                class="dxe-it__lab-thumb"
                :src="f.localPath"
                mode="aspectFill"
              />
              <view v-else class="dxe-it__lab-pdf">
                <gf-icon name="file" :size="56" color="#9A2D2D" />
                <text class="dxe-it__lab-pdf-tag gf-tnum">PDF</text>
              </view>
              <view class="dxe-it__lab-badge" :class="`is-${f.status}`">
                <view v-if="f.status === 'uploading'" class="dxe-it__lab-dot" />
                <gf-icon v-else-if="f.status === 'done'" name="check" :size="28" color="#5FB3A1" />
                <text v-else class="dxe-it__lab-retry" @tap.stop="emit('lab-retry', i)">重传</text>
              </view>
            </view>
            <view class="dxe-it__lab-del" @tap.stop="emit('lab-remove', i)">
              <gf-icon name="close" :size="28" color="#8A8275" />
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- 底部：开始辨证独占整行大 CTA -->
    <view class="dxe-it__cta-bar">
      <view
        class="dxe-it__cta"
        :class="{ 'is-disabled': !canSubmit }"
        hover-class="dxe-it__cta--hover"
        @tap="onSubmit"
      >
        开始辨证
      </view>
    </view>

    <!-- 录音浮层 -->
    <gf-rec-overlay
      v-if="recording || processing"
      :recording="recording"
      :processing="processing"
      :cancel-armed="cancelArmed"
      :seconds="seconds"
      :live-text="liveText"
    />

    <!-- 舌象取景预览层 -->
    <view v-if="showTonguePreview" class="dxe-tongue-mask" @touchmove.stop.prevent>
      <view class="dxe-tongue-stage">
        <image class="dxe-tongue-preview" :src="previewImg" mode="aspectFit" />
        <view class="dxe-tongue-guide" />
        <view class="dxe-tongue-hint">请将舌体置于框内 · 自然伸舌 · 光线充足</view>
      </view>
      <view class="dxe-tongue-actions gf-safe-bottom">
        <view class="dxe-tongue-btn dxe-tongue-btn--ghost" hover-class="dxe-tongue-btn--hover" @tap="retakeTongue">重拍</view>
        <view class="dxe-tongue-btn dxe-tongue-btn--primary" hover-class="dxe-tongue-btn--hover" @tap="confirmTongue">使用此张</view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.dxe-it {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;

  &__scroll {
    flex: 1;
    min-height: 0;
    padding: 24rpx var(--dxe-pad) 12rpx;
    box-sizing: border-box;
  }

  &__lead {
    display: flex;
    align-items: center;
    gap: 24rpx;
    margin-bottom: 28rpx;
  }
  &__seal {
    width: 104rpx;
    height: 104rpx;
    font-size: 52rpx;
  }
  &__title {
    font-size: var(--gf-fs-title);
    font-weight: 700;
    color: $ink;
  }
  &__sub {
    font-size: var(--gf-fs-sm);
    margin-top: 6rpx;
  }

  &__field {
    padding: 32rpx;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    &.is-focus {
      border-color: $cinnabar;
      box-shadow: 0 0 0 2rpx rgba(154, 45, 45, 0.18);
    }
  }
  &__textarea {
    width: 100%;
    min-height: 280rpx;
    font-size: var(--gf-fs-lg);
    line-height: var(--gf-lh);
    color: $ink;
  }
  &__ph {
    color: $ink-3;
    font-size: var(--gf-fs-base);
  }

  /* 输入方式大块 */
  &__tools {
    display: flex;
    gap: var(--dxe-gap);
    margin-top: 28rpx;
  }
  &__tool {
    flex: 1;
    min-height: 168rpx;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 14rpx;
    background: $paper-card;
    border: 2rpx solid $border-paper;
    border-radius: var(--dxe-radius);
    &.is-recording {
      background: $cinnabar;
      border-color: $cinnabar;
      .dxe-it__tool-text {
        color: $paper-card;
      }
    }
    &.is-off {
      opacity: 0.45;
    }
    &.is-done {
      border-color: $cinnabar;
    }
  }
  &__tool-text {
    font-size: var(--gf-fs-sm);
    color: $ink-2;
  }

  /* 常见主诉双列大块 */
  &__chips-label {
    font-size: var(--gf-fs-sm);
    margin: 40rpx 0 20rpx;
  }
  &__chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--dxe-gap);
  }
  &__chip {
    width: calc(50% - var(--dxe-gap) / 2);
    box-sizing: border-box;
    min-height: 104rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 22rpx 24rpx;
    background: $paper-card;
    border: 2rpx solid $border-paper;
    border-radius: var(--dxe-radius-sm);
    font-size: var(--gf-fs-base);
    color: $ink-2;
    &--hover {
      background: $paper-sunken;
      border-color: $gold;
      color: $cinnabar;
    }
  }

  /* 舌象缩略卡 */
  &__tongue-card {
    display: flex;
    align-items: flex-start;
    gap: 28rpx;
    padding: 28rpx;
    margin-top: 32rpx;
    transition: border-color 0.3s ease;
    &.is-done {
      border-color: rgba(95, 179, 161, 0.5);
    }
    &.is-retake {
      border-color: rgba(200, 164, 92, 0.6);
    }
  }
  &__tongue-figure {
    position: relative;
    width: 180rpx;
    height: 180rpx;
    flex-shrink: 0;
    border-radius: var(--dxe-radius-sm);
    overflow: hidden;
  }
  &__tongue-thumb {
    width: 100%;
    height: 100%;
    background: $paper-sunken;
    transition: filter 0.4s ease;
    &.is-analyzing {
      filter: grayscale(0.45) brightness(0.94);
    }
  }
  &__tongue-scan {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      180deg,
      transparent 0%,
      rgba(154, 45, 45, 0.32) 48%,
      rgba(200, 164, 92, 0.22) 52%,
      transparent 100%
    );
    transform: translateY(-100%);
    animation: dxeTongueScan 1.5s ease-in-out infinite;
  }
  &__tongue-stamp {
    position: absolute;
    right: 8rpx;
    bottom: 8rpx;
    width: 60rpx;
    height: 60rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 10rpx;
    font-size: var(--gf-fs-sm);
    color: $paper-card;
    background: $cinnabar;
    opacity: 0;
    transform: scale(0.6);
    &.is-pending {
      opacity: 0.5;
      animation: dxeTongueFloat 1.4s ease-in-out infinite;
    }
    &.is-set {
      opacity: 1;
      transform: scale(1);
      animation: dxeTongueSet 0.42s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
  }
  &__tongue-meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 16rpx;
  }
  &__tongue-ok,
  &__tongue-status,
  &__tongue-warn {
    display: flex;
    align-items: center;
    gap: 14rpx;
    font-size: var(--gf-fs-base);
    color: $ink;
  }
  &__tongue-warn {
    color: $gold;
  }
  &__tongue-desc {
    font-size: var(--gf-fs-sm);
    line-height: var(--gf-lh);
  }
  &__tongue-ops {
    display: flex;
    gap: var(--dxe-gap);
    margin-top: 4rpx;
  }
  &__tongue-op {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: var(--dxe-tap-h);
    padding: 0 36rpx;
    border-radius: 999rpx;
    border: 2rpx solid $dai-qing;
    font-size: var(--gf-fs-base);
    color: $dai-qing;
    &--del {
      border-color: $border-paper;
      color: $ink-3;
    }
    &--hover {
      background: $paper-sunken;
    }
  }

  /* 化验单卡 */
  &__lab-card {
    margin-top: 32rpx;
    padding: 28rpx;
  }
  &__lab-title {
    font-size: var(--gf-fs-base);
    color: $ink;
    margin-bottom: 20rpx;
  }
  &__lab-title-sub {
    font-size: var(--gf-fs-sm);
  }
  &__lab-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--dxe-gap);
  }
  &__lab-item {
    position: relative;
    width: 168rpx;
  }
  &__lab-figure {
    position: relative;
    width: 168rpx;
    height: 168rpx;
    border-radius: var(--dxe-radius-sm);
    overflow: hidden;
    background: $paper-sunken;
    border: 1px solid $border-paper;
  }
  &__lab-thumb {
    width: 100%;
    height: 100%;
  }
  &__lab-pdf {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8rpx;
  }
  &__lab-pdf-tag {
    font-size: 26rpx;
    font-weight: 700;
    letter-spacing: 1rpx;
    color: $ink-3;
  }
  &__lab-badge {
    position: absolute;
    left: 8rpx;
    bottom: 8rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 44rpx;
    height: 44rpx;
    padding: 0 10rpx;
    box-sizing: border-box;
    border-radius: 10rpx;
    background: rgba(251, 247, 238, 0.92);
    &.is-failed {
      background: $cinnabar;
    }
  }
  &__lab-dot {
    width: 18rpx;
    height: 18rpx;
    border-radius: 50%;
    background: $cinnabar;
    animation: dxeLabDot 0.9s ease-in-out infinite;
  }
  &__lab-retry {
    font-size: var(--gf-fs-sm);
    color: $paper-card;
  }
  &__lab-del {
    position: absolute;
    right: -10rpx;
    top: -10rpx;
    width: 52rpx;
    height: 52rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: $paper-card;
    border: 1px solid $border-paper;
  }

  /* 底部 CTA 独占整行 */
  &__cta-bar {
    padding: 16rpx var(--dxe-pad) env(safe-area-inset-bottom);
  }
  &__cta {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: var(--dxe-cta-h);
    border-radius: var(--dxe-radius);
    background: $cinnabar;
    color: $paper-card;
    font-size: var(--gf-fs-lg);
    font-weight: 600;
    box-sizing: border-box;
    &.is-disabled {
      opacity: 0.45;
    }
    &--hover {
      background: $cinnabar-soft;
    }
  }
}

@keyframes dxeLabDot {
  0%,
  100% {
    transform: scale(0.7);
    opacity: 0.5;
  }
  50% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 舌象取景预览层 */
.dxe-tongue-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: $navy-2;
  display: flex;
  flex-direction: column;
}
.dxe-tongue-stage {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.dxe-tongue-preview {
  width: 100%;
  height: 100%;
}
.dxe-tongue-guide {
  position: absolute;
  left: 50%;
  top: 44%;
  width: 460rpx;
  height: 580rpx;
  transform: translate(-50%, -50%);
  border: 2px dashed $gold;
  border-radius: 50%;
  animation: dxeTongueBreathe 2s ease-in-out infinite;
}
.dxe-tongue-hint {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 60rpx;
  text-align: center;
  font-size: var(--gf-fs-base);
  color: $on-navy-2;
  padding: 0 48rpx;
}
.dxe-tongue-actions {
  display: flex;
  gap: var(--dxe-gap);
  padding: 36rpx 40rpx;
  background: $navy-2;
}
.dxe-tongue-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 128rpx;
  border-radius: var(--dxe-radius-sm);
  font-size: var(--gf-fs-base);
  &--ghost {
    color: $on-navy;
    border: 2rpx solid rgba(255, 255, 255, 0.3);
  }
  &--primary {
    background: $cinnabar;
    color: $paper-card;
    font-weight: 600;
  }
  &--hover {
    opacity: 0.85;
  }
}

@keyframes dxeTongueBreathe {
  0%,
  100% {
    border-color: rgba(200, 164, 92, 0.5);
  }
  50% {
    border-color: rgba(200, 164, 92, 0.95);
  }
}
@keyframes dxeTongueScan {
  0% {
    transform: translateY(-100%);
  }
  100% {
    transform: translateY(100%);
  }
}
@keyframes dxeTongueFloat {
  0%,
  100% {
    transform: translateY(0) scale(0.92);
    opacity: 0.4;
  }
  50% {
    transform: translateY(-4rpx) scale(0.96);
    opacity: 0.6;
  }
}
@keyframes dxeTongueSet {
  0% {
    transform: scale(0.5) rotate(-8deg);
    opacity: 0.2;
  }
  100% {
    transform: scale(1) rotate(0);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dxe-tongue-guide {
    animation: none;
  }
  .dxe-it__tongue-scan {
    animation: none;
    opacity: 0.4;
  }
  .dxe-it__tongue-stamp.is-pending,
  .dxe-it__tongue-stamp.is-set {
    animation: none;
  }
  .dxe-it__lab-dot {
    animation: none;
  }
}
</style>
