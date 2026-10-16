# 李时珍智能医师 · 移动端

uni-app（Vue3 + Vite + TS）。最终面向 **微信小程序 / 公众号(H5) / H5**，当前轮次仅针对**微信小程序**，且仅搭建基础与「仿真辨证」骨架（不含业务逻辑）。

## 技术栈

| 项 | 选型 |
|---|---|
| 框架 | uni-app（Vue3 `createSSRApp` 写法） |
| 构建 | Vite 5 + TypeScript |
| 状态 | Pinia |
| UI 组件库 | [wot-design-uni](https://wot-design-uni.netlify.app/)（easycom 自动引入，主题色已对齐朱砂） |
| 样式 | SCSS + 设计 token（`src/uni.scss` 全局注入） |

## 运行

```bash
npm install
npm run dev:mp-weixin     # 生成 dist/dev/mp-weixin
```

用**微信开发者工具**导入 `dist/dev/mp-weixin`：

- `manifest.json` 的 `mp-weixin.appid` 当前为 **`wx5050c5867e49331c`**（正式 appid）→ 开发者工具需登录有该小程序权限的账号导入。
- 后端联调：`src/api/request.ts` 的 `API_BASE` 默认 `http://localhost:8000/api`，开发者工具需勾选「不校验合法域名」（`manifest` 已设 `urlCheck:false`）。

构建产物：`npm run build:mp-weixin`。

## 目录结构

```
src/
├─ uni.scss                  # 设计 token（双表面：宣纸面 + 藏青面），全局注入
├─ styles/global.scss        # 全局通用类（.gf-card / .gf-navy / .gf-seal / .gf-divider …）
├─ api/
│  ├─ request.ts             # uni.request 封装（baseURL/超时/错误）
│  └─ index.ts               # 业务 API（辨证/养生/慢病/知识/报告/语音 全量接入真实后端）
├─ components/
│  ├─ gf-icon/               # 国风细线 SVG 图标（与 PC 同源；小程序用 image+data-uri 渲染）
│  └─ gf-navbar/             # 古籍风自定义导航栏（接管状态栏占位；customBack 可拦截返回）
└─ pages/
   ├─ index/index.vue        # 首页 · 五大模块入口（全部启用）+ 技术架构条
   ├─ seasonal/index.vue     # 四时养生（四季切换+起居膳食情志功法，接 /regimen/seasonal）
   ├─ organ/index.vue        # 五脏调养（五行正色+食疗药膳药材节气，接 /regimen/organ）
   ├─ chronic/index.vue      # 慢病助手（适老大字+病种症状勾选+一键辨证，接 /chronic/*）
   ├─ knowledge/index.vue    # 知识检索（检索+分类+分页+详情，接 /knowledge/search·stats）
   └─ diagnose/             # V2 多模态问诊（全屏步进卡 + 异步任务 + 统一附件 + 实时语音）
      ├─ index.vue          #   编排：消费 useDiagnose（状态机 intake→inquiry→diagnosing→result）
      ├─ useDiagnose.ts     #   V2 会话流：prepare/answers/finalize 异步任务轮询
      ├─ types.ts / mock.ts #   类型（对齐后端）+ 常见主诉 chips
      └─ components/
         ├─ dx-intake.vue        # 录入卡：主诉+长按实时语音+统一医疗附件入口
         ├─ dx-question-card.vue # 问诊步进卡：single/multi/slider/text + 补充 + 翻卡
         ├─ dx-footprints.vue    # 足迹点（只显示走过的步，可跳转回退）
         ├─ dx-thinking.vue      # 斟酌过场（卡间等 inquiry 的脉动印章）
         ├─ dx-case-sheet.vue    # 脉案 bottom sheet（点条目回退重答）
         ├─ dx-decision.vue      # 决断过场（明→暗印章「四诊已明」+ 震动）
         └─ dx-result.vue        # 结果藏青长卷（八步淡入+锁定角色+候选bar+君臣佐使+溯源）
```

### 后端依赖（联调）

`api/request.ts` 的 `API_BASE` 指向 `http://localhost:8000/api`。消费接口（chat/regimen/chronic/knowledge/report）已在 8000 提供，养生类改过 JSON 的需重启加载。

**语音识别 = RecorderManager 音频帧 → 自有 WSS → Fun-ASR Realtime**：
- 每段录音先创建匿名 V2 会话，再通过 `/api/v2/asr/realtime` 转发 16kHz 单声道 MP3 帧；
- 百炼 Key 仅在后端，音频不落盘；实时/最终转写只追加到输入框，不自动提交；
- `manifest.json` 中 WechatSI 仅供现有报告朗读（TTS）使用，不再承担语音识别。

三轮核查报告见 `docs/核查报告.md`；各页设计文档见 `docs/*-设计.md`。

### 仿真辨证 · 交互要点（移动端第一准则）

- **全屏步进卡**：一屏一问，前进/后退用受控 transition（自右入/自左入，仅 transform+opacity）。
- **不预告步数**：足迹点只显示走过的步，绝不出现 X-Y 总数（问诊会被模型 ready 提前结束）。
- **答案快照**：提交后锁定本轮回答；后续信息可在下一问的补充说明中填写。
- **键盘**：textarea 用 `adjust-position`+`cursor-spacing` 避让；选择类题型不弹键盘。
- **长按语音**：`touchstart` 起录 → `touchmove` 上滑取消 → `touchend` 发送，带录音浮层+震动。
- **决断过场**：宣纸明→藏青暗 + 朱砂印章盖印 + `uni.vibrateShort`；尊重 `prefers-reduced-motion`。
- **结果**：问诊用步进卡，结果改藏青竖向长卷（雷达/君臣佐使需纵向空间）；患者视角隐藏剂量。

V2 API 已接入；`mock.ts` 只保留常见主诉等静态 UI 数据。

## UI 风格（与 PC 端统一）

事实来源：`../docs/UI设计规范.md`。双表面系统：

- **古籍宣纸面**（默认）：宣纸暖底 `#F3ECDD`、墨字、朱砂强调、金分隔 —— 懂行/文化/适老。
- **藏青数据面**（局部）：深色沉浸 `#1F3A5F` —— 用于仿真辨证「结果可视化区」，让图表发光。
- 强调色：朱砂 `#9A2D2D`（主 CTA/印章）、金 `#C8A45C`、黛青 `#34505C`、玉 `#5FB3A1`。
- 图标：统一 `gf-icon`，**禁用 emoji**；正文 ≥16px、触控目标 ≥44px；每页附医疗免责声明。

> 说明：小程序无法加载远程 Web 字体，标题宋体退化为系统 `Songti SC`，正文用系统无衬线。
