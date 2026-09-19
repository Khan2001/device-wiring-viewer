import { computed, ref } from "vue";
import { api } from "../api";
import type { ServiceState } from "../domain";

/** Keeps API and database status checks in one reusable UI boundary. */
export function useServiceHealth() {
  const apiState = ref<ServiceState>("checking");
  const dbState = ref<ServiceState>("checking");
  const ready = computed(() => apiState.value === "ok" && dbState.value === "ok");
  const label = computed(() =>
    apiState.value === "checking" || dbState.value === "checking"
      ? "检查中"
      : ready.value
        ? "已连接"
        : "连接异常"
  );

  async function checkHealth(): Promise<void> {
    apiState.value = "checking";
    dbState.value = "checking";
    try {
      const health = await api.get<{ status: string }>("/api/health");
      apiState.value = health.status === "ok" ? "ok" : "error";
    } catch {
      apiState.value = "error";
    }
    try {
      const health = await api.get<{ status: string }>("/api/health/db");
      dbState.value = health.status === "ok" ? "ok" : "error";
    } catch {
      dbState.value = "error";
    }
  }

  return { apiState, dbState, ready, label, checkHealth };
}
