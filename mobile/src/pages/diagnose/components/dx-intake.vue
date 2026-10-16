<script setup lang="ts">
import { ref, computed } from "vue";
import { COMMON_CHIEFS } from "../mock";
import { useVoiceInput } from "@/composables/useVoiceInput";

/**
 * 录入卡（宣纸面 · 全屏）。仿真辨证第一屏。
 * 交互重点：
 *  - 大字主诉输入，textarea 自动避让键盘（adjust-position + cursor-spacing）。
 *  - 常见主诉 chips：点一下追加到主诉，免打字（适老）。
 *  - 长按「按住说」语音：touchstart 起录 → touchmove 上滑取消 → touchend 结束。
 *  - 拍舌象：取景预览后即交上层「后台识别」，本卡只管取景与展示，不阻塞用户。
 *  - 朱砂 CTA，主诉为空时禁用。
 *
 * 舌象识别状态（tongueStatus/tongueImg/tongueDesc/tongueHint）由上层 useDiagnose 持有，
 * 因为识别要贯穿到问卷阶段；本卡通过 props 读、通过 emit 触发后台识别与删除。
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
    tongueDesc: string; // 识别成功的中医术语（tcm_text）
    tongueHint: string; // 需重拍 / 降级说明
    labFiles?: LabFile[]; // 化验单列表（上层透传）
  }>(),
  { labFiles: () => [] }
);
const emit = defineEmits<{
  (e: "submit", chief: string): void;
  (e: "tongue-confirm", filePath: string): void; // 取景确认 → 上层后台识别
  (e: "tongue-remove"): void; // 删除舌象
  (e: "lab-add", items: { path: string; isPdf: boolean }[]): void; // 选定化验单 → 上层上传
  (e: "lab-remove", index: number): void; // 删除某项化验单
  (e: "lab-retry", index: number): void; // 重传某项化验单
}>();

const chief = ref("");
const focused = ref(false);
const canSubmit = computed(() => chief.value.trim().length > 0);

/* —— 舌象拍照（取景预览为本卡本地 UI；已采集状态由 props 驱动） —— */
const previewImg = ref(""); // 取景预览图
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
    fail: () => {
      /* 用户取消 / 拒绝授权：静默，保留手动流程 */
    },
  });
}
function retakeTongue() {
  showTonguePreview.value = false;
  previewImg.value = "";
  chooseTongue();
}
/** 确认此张：先把照片交给上层开始上传，再收起取景层——不再弹全屏 loading 卡住用户。
 *  顺序要紧：H5 下 previewImg 是 blob: URL，由预览 <image> 持有；若先清空再上传，
 *  uni.uploadFile 异步读取时 blob 可能已失效 → 传出空文件。故先 emit 起传，后拆预览。 */
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
  else if (cur.includes(text)) return; // 已含则不重复
  else chief.value = cur + (/[。！？；，,.!?;]$/.test(cur) ? "" : "，") + text;
}

function onSubmit() {
  if (!canSubmit.value) {
    uni.showToast({ title: "请先描述主要不适", icon: "none" });
    return;
  }
  // 只交主诉原文；舌象注入由 useDiagnose 在每次请求时按当前识别状态拼接，
  // 这样后台识别即便此刻未完成，决断前也能补上 tcm_text。
  emit("submit", chief.value.trim());
}

/* —— 长按语音 → 端侧识别（逻辑搬到 useVoiceInput composable，交互与原一致） —— */
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

/* —— 统一附件入口：图片/PDF 均由后端自动分类为舌象、报告、处方或病历 —— */
function chooseLab() {
  // 微信端两条入口；非微信端仅留选图（chooseMessageFile 不可用）。
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
    fail: () => {
      /* 取消：静默 */
    },
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
    fail: () => {
      /* 取消 / 拒绝授权：静默 */
    },
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
    fail: () => {
      /* 取消：静默 */
    },
  });
  // #endif
}
</script>

<template>
  <view class="intake">
    <!-- 引导 -->
    <view class="intake__lead">
      <view class="intake__seal gf-seal gf-serif">问</view>
      <view class="intake__lead-text">
        <view class="intake__title gf-serif">请描述您的主要不适</view>
        <view class="intake__sub gf-ink-3">说得越具体，辨证越准</view>
      </view>
    </view>

    <!-- 主诉输入 -->
    <view class="intake__field gf-card" :class="{ 'is-focus': focused }">
      <textarea
        v-model="chief"
        class="intake__textarea"
        :maxlength="-1"
        :auto-height="true"
        :adjust-position="true"
        :cursor-spacing="24"
        :show-confirm-bar="false"
        placeholder="如：失眠三个月，入睡困难，夜里多梦易醒…"
        placeholder-class="intake__ph"
        @focus="focused = true"
        @blur="focused = false"
      />
    </view>

    <!-- 常见主诉 chips -->
    <view class="intake__chips-label gf-ink-3">常见主诉 · 点选快速填入</view>
    <view class="intake__chips">
      <view
        v-for="c in COMMON_CHIEFS"
        :key="c"
        class="intake__chip"
        hover-class="intake__chip--hover"
        :hover-stay-time="60"
        @tap="appendChief(c)"
      >{{ c }}</view>
    </view>

    <!-- 舌象缩略图卡（后台识别中也可继续填写，不阻塞） -->
    <view v-if="tongueImg" class="intake__tongue-card gf-card" :class="`is-${tongueStatus}`">
      <view class="intake__tongue-figure">
        <image
          class="intake__tongue-thumb"
          :class="{ 'is-analyzing': tongueStatus === 'analyzing' }"
          :src="tongueImg"
          mode="aspectFill"
        />
        <!-- 识别中：朱砂墨色扫光 -->
        <view v-if="tongueStatus === 'analyzing'" class="intake__tongue-scan" />
        <!-- 「舌」印：识别中半透浮动，识别成功弹簧落定 -->
        <view
          class="intake__tongue-stamp gf-serif"
          :class="{
            'is-pending': tongueStatus === 'analyzing',
            'is-set': tongueStatus === 'done',
          }"
        >舌</view>
      </view>
      <view class="intake__tongue-meta">
        <!-- 识别中 -->
        <view v-if="tongueStatus === 'analyzing'" class="intake__tongue-status gf-serif">
          <text>舌象识别中</text>
          <view class="intake__tongue-dots">
            <view
              v-for="i in 3"
              :key="i"
              class="intake__tongue-dot"
              :style="{ animationDelay: i * 0.16 + 's' }"
            />
          </view>
        </view>
        <!-- 识别成功 -->
        <view v-else-if="tongueStatus === 'done'" class="intake__tongue-ok gf-serif">
          <gf-icon name="check" :size="28" color="#5FB3A1" />
          <text>舌象已识别</text>
        </view>
        <!-- 需重拍 -->
        <view v-else-if="tongueStatus === 'retake'" class="intake__tongue-warn gf-serif">
          <text>建议重拍</text>
        </view>
        <!-- 降级保留 -->
        <view v-else class="intake__tongue-ok gf-serif">
          <gf-icon name="check" :size="28" color="#A99" />
          <text>舌象照片已保留</text>
        </view>

        <!-- 说明文案 -->
        <view v-if="tongueStatus === 'done' && tongueDesc" class="intake__tongue-desc gf-ink-2">
          {{ tongueDesc }}
        </view>
        <view v-else-if="tongueStatus === 'analyzing'" class="intake__tongue-desc gf-ink-3">
          识别在后台进行，您可以继续往下填
        </view>
        <view
          v-else-if="(tongueStatus === 'retake' || tongueStatus === 'degraded') && tongueHint"
          class="intake__tongue-desc gf-ink-3"
        >
          {{ tongueHint }}
        </view>

        <view class="intake__tongue-ops">
          <text class="intake__tongue-op" @tap="chooseTongue">重拍</text>
          <text class="intake__tongue-op intake__tongue-op--del" @tap="removeTongue">删除</text>
        </view>
      </view>
    </view>

    <!-- 化验单缩略图卡（原图直送辨证，不做识别；上传中/已上传/失败可重传） -->
    <view v-if="labFiles.length" class="intake__lab-card gf-card">
      <view class="intake__lab-title gf-serif">
        医疗附件 · {{ labFiles.length }} 份
        <text class="intake__lab-title-sub gf-ink-3">（自动识别类型，仅作问诊参考）</text>
      </view>
      <view class="intake__lab-list">
        <view v-for="(f, i) in labFiles" :key="i" class="intake__lab-item">
          <!-- 缩略：图片显图，PDF 显报告单图标占位 -->
          <view class="intake__lab-figure">
            <image
              v-if="!f.isPdf"
              class="intake__lab-thumb"
              :src="f.localPath"
              mode="aspectFill"
            />
            <view v-else class="intake__lab-pdf">
              <gf-icon name="file" :size="44" color="#9A2D2D" />
              <text class="intake__lab-pdf-tag gf-tnum">PDF</text>
            </view>
            <!-- 状态角标 -->
            <view class="intake__lab-badge" :class="`is-${f.status}`">
              <view v-if="f.status === 'uploading'" class="intake__lab-dot" />
              <gf-icon v-else-if="f.status === 'done'" name="check" :size="22" color="#5FB3A1" />
              <text v-else class="intake__lab-retry" @tap.stop="emit('lab-retry', i)">重传</text>
            </view>
          </view>
          <!-- 删除 -->
          <view class="intake__lab-del" @tap.stop="emit('lab-remove', i)">
            <gf-icon name="close" :size="22" color="#8A8275" />
          </view>
        </view>
      </view>
    </view>

    <view class="intake__spacer" />

    <!-- 底部工具 + CTA -->
    <view class="intake__actions">
      <view
        class="intake__voice"
        :class="{ 'is-recording': recording, 'is-off': !voiceSupported }"
        @touchstart.stop.prevent="onPressStart"
        @touchmove.stop.prevent="onPressMove"
        @touchend.stop.prevent="onPressEnd"
        @touchcancel.stop.prevent="onPressEnd"
      >
        <gf-icon name="mic" :size="40" color="#5C5345" />
        <text class="intake__voice-text">按住说</text>
      </view>
      <view class="intake__tongue" :class="{ 'is-done': labFiles.length }" @tap="chooseLab">
        <gf-icon name="file" :size="40" :color="labFiles.length ? '#9A2D2D' : '#5C5345'" />
        <text class="intake__tongue-text">{{ labFiles.length ? `附件 ${labFiles.length}` : "上传附件" }}</text>
      </view>
      <view
        class="intake__cta gf-btn gf-btn-primary"
        :class="{ 'is-disabled': !canSubmit }"
        hover-class="intake__cta--hover"
        @tap="onSubmit"
      >
        开始辨证
      </view>
    </view>

    <!-- 长按录音 / 转写浮层（由 composable 状态驱动） -->
    <gf-rec-overlay
      v-if="recording || processing"
      :recording="recording"
      :processing="processing"
      :cancel-armed="cancelArmed"
      :seconds="seconds"
      :live-text="liveText"
    />

    <!-- 舌象取景预览层（catchtouchmove 防滚动穿透） -->
    <view v-if="showTonguePreview" class="tongue-mask" @touchmove.stop.prevent>
      <view class="tongue-stage">
        <image class="tongue-preview" :src="previewImg" mode="aspectFit" />
        <view class="tongue-guide" />
        <view class="tongue-hint">请将舌体置于框内 · 自然伸舌 · 光线充足</view>
      </view>
      <view class="tongue-actions gf-safe-bottom">
        <view class="tongue-btn tongue-btn--ghost" hover-class="tongue-btn--hover" @tap="retakeTongue">重拍</view>
        <view class="tongue-btn tongue-btn--primary" hover-class="tongue-btn--hover" @tap="confirmTongue">使用此张</view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.intake {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24rpx 32rpx;
  box-sizing: border-box;

  &__lead {
    display: flex;
    align-items: center;
    gap: 20rpx;
    margin-bottom: 24rpx;
  }
  &__seal {
    width: 72rpx;
    height: 72rpx;
    font-size: 38rpx;
  }
  &__title {
    font-size: 40rpx;
    font-weight: 700;
    color: $ink;
  }
  &__sub {
    font-size: 26rpx;
    margin-top: 2rpx;
  }

  &__field {
    padding: 24rpx;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    &.is-focus {
      border-color: $cinnabar;
      box-shadow: 0 0 0 2rpx rgba(154, 45, 45, 0.18);
    }
  }
  &__textarea {
    width: 100%;
    min-height: 200rpx;
    font-size: 34rpx;
    line-height: 1.6;
    color: $ink;
  }
  &__ph {
    color: $ink-3;
    font-size: 32rpx;
  }

  &__chips-label {
    font-size: 24rpx;
    margin: 28rpx 0 14rpx;
  }
  &__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 16rpx;
  }
  &__chip {
    padding: 14rpx 28rpx;
    background: $paper-card;
    border: 1px solid $border-paper;
    border-radius: 999rpx;
    font-size: 28rpx;
    color: $ink-2;
    &--hover {
      background: $paper-sunken;
      border-color: $gold;
      color: $cinnabar;
    }
  }

  &__spacer {
    flex: 1;
    min-height: 24rpx;
  }

  /* 底部操作区 */
  &__actions {
    display: flex;
    align-items: stretch;
    gap: 16rpx;
    padding-bottom: env(safe-area-inset-bottom);
  }
  &__voice,
  &__tongue {
    width: 120rpx;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6rpx;
    background: $paper-card;
    border: 1px solid $border-paper;
    border-radius: $radius-sm;
    flex-shrink: 0;
  }
  &__voice.is-recording {
    background: $cinnabar;
    border-color: $cinnabar;
    .intake__voice-text {
      color: $paper-card;
    }
  }
  /* 不支持语音：置灰（onPressStart 已含「请打字输入」toast） */
  &__voice.is-off {
    opacity: 0.45;
  }
  &__tongue.is-done {
    border-color: $cinnabar;
  }
  &__voice-text,
  &__tongue-text {
    font-size: 24rpx;
    color: $ink-2;
  }

  /* 舌象缩略图卡 */
  &__tongue-card {
    display: flex;
    align-items: center;
    gap: 24rpx;
    padding: 20rpx;
    margin-top: 24rpx;
    transition: border-color 0.3s ease;
    &.is-done {
      border-color: rgba(95, 179, 161, 0.5);
    }
    &.is-retake {
      border-color: rgba(200, 164, 92, 0.6);
    }
  }
  /* 缩略图 + 扫光 + 印章的舞台 */
  &__tongue-figure {
    position: relative;
    width: 120rpx;
    height: 120rpx;
    flex-shrink: 0;
    border-radius: $radius-sm;
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
  /* 朱砂墨色扫光：识别中自上而下循环晕染 */
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
    animation: tongueScan 1.5s ease-in-out infinite;
  }
  /* 「舌」印：识别中半透浮动，成功弹簧落定 */
  &__tongue-stamp {
    position: absolute;
    right: 6rpx;
    bottom: 6rpx;
    width: 44rpx;
    height: 44rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8rpx;
    font-size: 28rpx;
    color: $paper-card;
    background: $cinnabar;
    opacity: 0;
    transform: scale(0.6);
    &.is-pending {
      opacity: 0.5;
      animation: tongueStampFloat 1.4s ease-in-out infinite;
    }
    &.is-set {
      opacity: 1;
      transform: scale(1);
      animation: tongueStampSet 0.42s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
  }
  &__tongue-meta {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 12rpx;
  }
  &__tongue-ok,
  &__tongue-status,
  &__tongue-warn {
    display: flex;
    align-items: center;
    gap: 10rpx;
    font-size: 30rpx;
    color: $ink;
  }
  &__tongue-warn {
    color: $gold;
  }
  &__tongue-dots {
    display: flex;
    gap: 8rpx;
    align-items: center;
  }
  &__tongue-dot {
    width: 10rpx;
    height: 10rpx;
    border-radius: 50%;
    background: $cinnabar;
    animation: tongueDot 1s ease-in-out infinite;
  }
  &__tongue-desc {
    font-size: 26rpx;
    line-height: 1.5;
  }
  &__tongue-ops {
    display: flex;
    gap: 28rpx;
  }
  &__tongue-op {
    font-size: 28rpx;
    color: $dai-qing;
    &--del {
      color: $ink-3;
    }
  }
  /* 化验单缩略图卡 */
  &__lab-card {
    margin-top: 24rpx;
    padding: 20rpx;
  }
  &__lab-title {
    font-size: 28rpx;
    color: $ink;
    margin-bottom: 16rpx;
  }
  &__lab-title-sub {
    font-size: 22rpx;
  }
  &__lab-list {
    display: flex;
    flex-wrap: wrap;
    gap: 20rpx;
  }
  &__lab-item {
    position: relative;
    width: 120rpx;
  }
  &__lab-figure {
    position: relative;
    width: 120rpx;
    height: 120rpx;
    border-radius: $radius-sm;
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
    gap: 6rpx;
  }
  &__lab-pdf-tag {
    font-size: 20rpx;
    font-weight: 700;
    letter-spacing: 1rpx;
    color: $ink-3;
  }
  /* 状态角标：左下角 */
  &__lab-badge {
    position: absolute;
    left: 6rpx;
    bottom: 6rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 32rpx;
    height: 32rpx;
    padding: 0 6rpx;
    box-sizing: border-box;
    border-radius: 8rpx;
    background: rgba(251, 247, 238, 0.92);
    &.is-failed {
      background: $cinnabar;
    }
  }
  &__lab-dot {
    width: 14rpx;
    height: 14rpx;
    border-radius: 50%;
    background: $cinnabar;
    animation: labDot 0.9s ease-in-out infinite;
  }
  &__lab-retry {
    font-size: 22rpx;
    color: $paper-card;
  }
  /* 删除：右上角 */
  &__lab-del {
    position: absolute;
    right: -8rpx;
    top: -8rpx;
    width: 36rpx;
    height: 36rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: $paper-card;
    border: 1px solid $border-paper;
  }

  &__cta {
    flex: 1;
    min-height: auto;
    &.is-disabled {
      opacity: 0.45;
    }
    &--hover {
      background: $cinnabar-soft;
    }
  }
}

@keyframes labDot {
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
.tongue-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: $navy-2;
  display: flex;
  flex-direction: column;
}
.tongue-stage {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.tongue-preview {
  width: 100%;
  height: 100%;
}
.tongue-guide {
  position: absolute;
  left: 50%;
  top: 44%;
  width: 360rpx;
  height: 460rpx;
  transform: translate(-50%, -50%);
  border: 2px dashed $gold;
  border-radius: 50%;
  animation: tongueBreathe 2s ease-in-out infinite;
}
.tongue-hint {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 48rpx;
  text-align: center;
  font-size: 28rpx;
  color: $on-navy-2;
  padding: 0 48rpx;
}
.tongue-actions {
  display: flex;
  gap: 24rpx;
  padding: 28rpx 32rpx;
  background: $navy-2;
}
.tongue-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 96rpx;
  border-radius: $radius-sm;
  font-size: 32rpx;
  &--ghost {
    color: $on-navy;
    border: 1px solid rgba(255, 255, 255, 0.3);
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
@keyframes tongueBreathe {
  0%,
  100% {
    border-color: rgba(200, 164, 92, 0.5);
  }
  50% {
    border-color: rgba(200, 164, 92, 0.95);
  }
}

/* 舌象后台识别动效 */
@keyframes tongueScan {
  0% {
    transform: translateY(-100%);
  }
  100% {
    transform: translateY(100%);
  }
}
@keyframes tongueStampFloat {
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
@keyframes tongueStampSet {
  0% {
    transform: scale(0.5) rotate(-8deg);
    opacity: 0.2;
  }
  100% {
    transform: scale(1) rotate(0);
    opacity: 1;
  }
}
@keyframes tongueDot {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  50% {
    transform: translateY(-8rpx);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .tongue-guide {
    animation: none;
  }
  .intake__tongue-scan {
    animation: none;
    opacity: 0.4;
  }
  .intake__tongue-stamp.is-pending,
  .intake__tongue-stamp.is-set {
    animation: none;
  }
  .intake__tongue-dot {
    animation: none;
  }
  .intake__lab-dot {
    animation: none;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  /* 引导区 */
  .intake__seal {
    width: 96rpx;
    height: 96rpx;
    font-size: 50rpx;
  }
  .intake__title {
    font-size: var(--gf-fs-title);
  }
  .intake__sub {
    font-size: var(--gf-fs-sm);
    margin-top: 4rpx;
  }

  /* 主诉大字输入 */
  .intake__field {
    padding: 32rpx;
  }
  .intake__textarea {
    min-height: 280rpx;
    font-size: var(--gf-fs-lg);
    line-height: var(--gf-lh);
  }
  .intake__ph {
    font-size: var(--gf-fs-base);
  }

  /* 常见主诉 chips：更宽松、更大字 */
  .intake__chips-label {
    font-size: var(--gf-fs-sm);
    margin: 36rpx 0 20rpx;
  }
  .intake__chips {
    gap: 24rpx;
  }
  .intake__chip {
    min-height: 88rpx;
    padding: 22rpx 40rpx;
    font-size: var(--gf-fs-base);
  }

  /* 底部交互按钮：录音 / 拍照 ≥112rpx */
  .intake__actions {
    gap: 24rpx;
  }
  .intake__voice,
  .intake__tongue {
    width: 160rpx;
    min-height: 160rpx;
    gap: 10rpx;
  }
  .intake__voice-text,
  .intake__tongue-text {
    font-size: var(--gf-fs-sm);
  }

  /* 舌象缩略卡 */
  .intake__tongue-card {
    gap: 32rpx;
    padding: 28rpx;
    margin-top: 32rpx;
  }
  .intake__tongue-figure {
    width: 160rpx;
    height: 160rpx;
  }
  .intake__tongue-stamp {
    width: 56rpx;
    height: 56rpx;
    font-size: var(--gf-fs-sm);
  }
  .intake__tongue-meta {
    gap: 16rpx;
  }
  .intake__tongue-ok,
  .intake__tongue-status,
  .intake__tongue-warn {
    font-size: var(--gf-fs-base);
    gap: 14rpx;
  }
  .intake__tongue-desc {
    font-size: var(--gf-fs-sm);
    line-height: var(--gf-lh);
  }
  .intake__tongue-ops {
    gap: 40rpx;
  }
  .intake__tongue-op {
    font-size: var(--gf-fs-base);
  }

  /* 舌象取景层 */
  .tongue-guide {
    width: 460rpx;
    height: 580rpx;
  }
  .tongue-hint {
    font-size: var(--gf-fs-base);
    bottom: 60rpx;
  }
  .tongue-actions {
    gap: 32rpx;
    padding: 36rpx 40rpx;
  }
  .tongue-btn {
    min-height: 128rpx;
    font-size: var(--gf-fs-base);
  }

  /* 化验单上传（团队新功能）*/
  .intake__lab-title { font-size: var(--gf-fs-base); }
  .intake__lab-title-sub { font-size: var(--gf-fs-sm); }
  .intake__lab-pdf-tag { font-size: 26rpx; }
  .intake__lab-retry { font-size: var(--gf-fs-sm); min-height: 56rpx; padding: 0 20rpx; }
}
</style>
