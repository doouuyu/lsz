/**
 * 全局角色 store（Pinia）。
 * 角色（患者 / 医师 / 研究者）是「自适应交互界面」的核心开关：
 *   - 决定向后端 /chat/diagnose 传的 role —— 后端据此切提示词，生成三套文风/侧重（白话食疗 / 术语剂量 / 文献溯源）。
 *   - 全局、持久、可跨页（仿真辨证、慢病助手等共用），切换不再随出结果重置。
 * 与 settings.ts（老年模式）同构：本地存储持久化，首启回灌。
 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import type { Role } from "@/pages/diagnose/types";

export type { Role };

const STORAGE_KEY = "lsz.role.v1";
const VALID: Role[] = ["patient", "doctor", "researcher"];
/** 默认医师：与现状「请求用 doctor 取全量」兼容，信息最完整。 */
const DEFAULT_ROLE: Role = "doctor";

function loadPersisted(): Role {
  try {
    const raw = uni.getStorageSync(STORAGE_KEY);
    if (typeof raw === "string" && VALID.includes(raw as Role)) return raw as Role;
  } catch {
    /* 读取失败回退默认 */
  }
  return DEFAULT_ROLE;
}

export const useRoleStore = defineStore("role", () => {
  const role = ref<Role>(loadPersisted());

  const isPatient = computed(() => role.value === "patient");
  const isDoctor = computed(() => role.value === "doctor");
  const isResearcher = computed(() => role.value === "researcher");

  function persist() {
    try {
      uni.setStorageSync(STORAGE_KEY, role.value);
    } catch {
      /* 持久化失败忽略，不阻塞交互 */
    }
  }

  function setRole(r: Role) {
    if (!VALID.includes(r) || r === role.value) return;
    role.value = r;
    persist();
  }

  return { role, isPatient, isDoctor, isResearcher, setRole };
});
