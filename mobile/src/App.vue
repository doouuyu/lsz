<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";

onLaunch(() => {
  console.log("App Launch · 李时珍智能医师");
});
onShow(() => {});
onHide(() => {});
</script>

<style lang="scss">
/* 全局双表面样式（编译为 app.wxss，全页面生效） */
@import "@/styles/global.scss";
</style>
