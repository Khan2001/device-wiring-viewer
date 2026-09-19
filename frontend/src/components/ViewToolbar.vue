<script setup lang="ts">
import { Expand, ZoomIn, ZoomOut } from "@element-plus/icons-vue";
import type { DeviceFace, ViewMode } from "../domain";

// Navigation is presentation-only; the page owns selection and persistence.
defineProps<{
  viewMode: ViewMode;
  deviceFace: DeviceFace;
  hasCabinet: boolean;
  hasDevice: boolean;
  zoom: number;
  snapToGrid: boolean;
  roomTitle: string;
  projectName?: string;
  cabinetCode?: string;
  deviceName?: string;
}>();

const emit = defineEmits<{
  "set-view": [mode: ViewMode];
  "set-face": [face: DeviceFace];
  "zoom": [delta: number];
  "update:snapToGrid": [value: boolean];
  fit: [];
}>();
</script>

<template>
  <div class="toolbar">
    <div>
      <el-breadcrumb separator="/">
        <el-breadcrumb-item>{{ projectName }}</el-breadcrumb-item>
        <el-breadcrumb-item :class="{ 'is-clickable': viewMode !== 'room' }" @click="emit('set-view', 'room')">{{ roomTitle }}</el-breadcrumb-item>
        <el-breadcrumb-item v-if="cabinetCode" :class="{ 'is-clickable': viewMode === 'device' }" @click="emit('set-view', 'cabinet')">{{ cabinetCode }}</el-breadcrumb-item>
        <el-breadcrumb-item v-if="viewMode === 'device' && deviceName">{{ deviceName }}</el-breadcrumb-item>
      </el-breadcrumb>
      <p class="view-hint">{{ viewMode === "room" ? "机房平面图 · 拖动机柜调整位置" : viewMode === "cabinet" ? "机柜正面 / 背面 · 点击设备查看接口" : "设备面板 · 单击网格新增接口，点击两个接口创建连接" }}</p>
    </div>
    <div class="toolbar-actions">
      <el-button-group>
        <el-button :type="viewMode === 'room' ? 'primary' : 'default'" @click="emit('set-view', 'room')">机房</el-button>
        <el-button :type="viewMode === 'cabinet' ? 'primary' : 'default'" :disabled="!hasCabinet" @click="emit('set-view', 'cabinet')">机柜</el-button>
        <el-button :type="viewMode === 'device' ? 'primary' : 'default'" :disabled="!hasDevice" @click="emit('set-view', 'device')">设备</el-button>
      </el-button-group>
      <el-button-group v-if="viewMode === 'device'">
        <el-button :type="deviceFace === 'front' ? 'primary' : 'default'" @click="emit('set-face', 'front')">正面</el-button>
        <el-button :type="deviceFace === 'back' ? 'primary' : 'default'" @click="emit('set-face', 'back')">背面</el-button>
      </el-button-group>
      <template v-if="viewMode !== 'cabinet'">
        <el-tooltip content="缩小"><el-button circle aria-label="缩小" @click="emit('zoom', -0.1)"><el-icon><ZoomOut /></el-icon></el-button></el-tooltip>
        <span class="zoom-value">{{ Math.round(zoom * 100) }}%</span>
        <el-tooltip content="放大"><el-button circle aria-label="放大" @click="emit('zoom', 0.1)"><el-icon><ZoomIn /></el-icon></el-button></el-tooltip>
      </template>
      <el-switch v-if="viewMode === 'room'" :model-value="snapToGrid" inline-prompt active-text="吸附" inactive-text="自由" @update:model-value="emit('update:snapToGrid', $event)" />
      <el-tooltip v-if="viewMode === 'room'" content="适配画布"><el-button plain aria-label="适配画布" @click="emit('fit')"><el-icon><Expand /></el-icon>适配</el-button></el-tooltip>
    </div>
  </div>
</template>
