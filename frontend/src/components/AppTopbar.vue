<script setup lang="ts">
import { ref } from "vue";
import {
  ArrowDown,
  Document,
  Download,
  FolderOpened,
  Picture,
  Refresh,
  Search,
  Upload
} from "@element-plus/icons-vue";

// The top bar emits user intent; file and health operations remain in App.vue.
defineProps<{
  saving: boolean;
  serviceReady: boolean;
  serviceLabel: string;
  searchQuery: string;
}>();

const emit = defineEmits<{
  "update:searchQuery": [value: string];
  search: [];
  "file-command": [command: string];
  "check-health": [];
  "import-selected": [event: Event];
}>();

const importInput = ref<HTMLInputElement>();

function chooseImport(): void {
  importInput.value?.click();
}

function handleFileCommand(command: string): void {
  if (command === "import") {
    chooseImport();
    return;
  }
  emit("file-command", command);
}
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark">DW</div>
      <div>
        <p class="eyebrow">设备接线台账</p>
        <h1>二维可视化编辑器</h1>
      </div>
    </div>
    <div class="top-actions">
      <el-tag :type="saving ? 'warning' : serviceReady ? 'success' : 'danger'" effect="plain">
        {{ saving ? "保存中" : serviceLabel }}
      </el-tag>
      <el-input
        class="search-input"
        :model-value="searchQuery"
        clearable
        placeholder="搜索设备、IP、接口"
        @update:model-value="emit('update:searchQuery', $event)"
        @keyup.enter="emit('search')"
      >
        <template #append><el-button aria-label="搜索" @click="emit('search')"><el-icon><Search /></el-icon></el-button></template>
      </el-input>
      <el-dropdown trigger="click" @command="handleFileCommand">
        <el-button size="small" plain>
          <el-icon><FolderOpened /></el-icon>文件<el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="import"><el-icon><Upload /></el-icon>导入 JSON</el-dropdown-item>
            <el-dropdown-item command="export-json" divided><el-icon><Document /></el-icon>导出 JSON</el-dropdown-item>
            <el-dropdown-item command="export-svg"><el-icon><Picture /></el-icon>导出 SVG</el-dropdown-item>
            <el-dropdown-item command="export-png"><el-icon><Download /></el-icon>导出 PNG</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-tooltip content="检查服务状态">
        <el-button size="small" circle plain aria-label="检查服务" @click="emit('check-health')"><el-icon><Refresh /></el-icon></el-button>
      </el-tooltip>
      <input ref="importInput" class="hidden-input" type="file" accept="application/json,.json" @change="emit('import-selected', $event)" />
    </div>
  </header>
</template>
