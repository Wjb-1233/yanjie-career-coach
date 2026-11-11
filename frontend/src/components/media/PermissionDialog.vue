<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, useTemplateRef } from 'vue'

/**
 * 摄像头/麦克风授权的两级提示：
 * - waiting：getUserMedia 已发起，等用户在浏览器原生弹窗点「允许」，不可关闭（父组件在成功/失败/超时后移除）
 * - denied：浏览器不会再弹窗（之前拒绝过），给出三步站点设置指引 + 一键重新检测
 */
const props = defineProps<{
  variant: 'waiting' | 'denied'
  devices: Array<'camera' | 'microphone'>
  notice?: string
}>()
const emit = defineEmits<{ retry: []; close: [] }>()
const dialog = useTemplateRef<HTMLDialogElement>('dialog')

const deviceLabel = computed(() => {
  const camera = props.devices.includes('camera')
  const mic = props.devices.includes('microphone')
  if (camera && mic) return '摄像头和麦克风'
  return camera ? '摄像头' : '麦克风'
})

const settingsTargets = computed(() => {
  const camera = props.devices.includes('camera')
  const mic = props.devices.includes('microphone')
  if (camera && mic) return '「摄像头」和「麦克风」'
  return camera ? '「摄像头」' : '「麦克风」'
})

onMounted(() => dialog.value?.showModal())
onBeforeUnmount(() => {
  if (dialog.value?.open) dialog.value.close()
})
</script>

<template>
  <dialog ref="dialog" class="perm-dialog" :class="variant" :aria-labelledby="`perm-title-${variant}`" @cancel.prevent>
    <div v-if="variant === 'waiting'" class="perm-body">
      <span class="perm-spinner" aria-hidden="true" />
      <h2 id="perm-title-waiting">等待你在浏览器里点「允许」</h2>
      <p class="perm-lead">已发起请求：浏览器弹出了{{ deviceLabel }}的授权窗口，请点「允许」。允许后这里会自动打开预览。</p>
      <p class="perm-hint">授权窗口一般在地址栏下方，或在地址栏右侧的图标里；如果浏览器把它折叠了，注意右上角有没有一个小的提示条。</p>
      <p v-if="notice" class="perm-notice" role="status">{{ notice }}</p>
      <span class="perm-progress" aria-hidden="true"><i /></span>
    </div>

    <div v-else class="perm-body">
      <p class="perm-eyebrow">需要改一下站点设置</p>
      <h2 id="perm-title-denied">浏览器不会再自动弹窗了</h2>
      <p class="perm-lead">
        这个站点之前拒绝过{{ deviceLabel }}授权，浏览器会记住这个选择，再点按钮也不会弹出授权窗口。
        按下面三步把站点设置改成「允许」，就能继续。
      </p>
      <ol class="perm-steps">
        <li>
          <span class="perm-num" aria-hidden="true">1</span>
          <div>
            <strong>点地址栏左侧的图标</strong>
            <small>锁形、调节滑块，或带斜线的摄像头图标</small>
          </div>
        </li>
        <li>
          <span class="perm-num" aria-hidden="true">2</span>
          <div>
            <strong>打开「站点设置」</strong>
            <small>把{{ settingsTargets }}从「拒绝」改成「允许」</small>
          </div>
        </li>
        <li>
          <span class="perm-num" aria-hidden="true">3</span>
          <div>
            <strong>回到本页点「我已改好，重新检测」</strong>
            <small>会重新发起一次授权请求，并刷新下方显示的权限状态</small>
          </div>
        </li>
      </ol>
      <p v-if="notice" class="perm-notice" role="status">{{ notice }}</p>
      <div class="perm-actions">
        <button class="button secondary" type="button" @click="emit('close')">先关闭</button>
        <button class="button" type="button" @click="emit('retry')">我已改好，重新检测</button>
      </div>
    </div>
  </dialog>
</template>

<style scoped>
.perm-dialog {
  width: min(480px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--card);
  color: var(--text);
  box-shadow: var(--shadow);
  animation: perm-in .18s var(--ease) both;
}
.perm-dialog::backdrop { background: rgba(3, 7, 18, .72); }
.perm-body { display: grid; justify-items: start; gap: 12px; padding: 28px; }
.perm-body h2 { margin: 0; font-size: 20px; line-height: 1.4; font-weight: 700; }
.perm-lead { margin: 0; color: var(--text-2); font-size: 14px; line-height: 1.75; }
.perm-hint { margin: 0; color: var(--text-3); font-size: 14px; line-height: 1.7; }
.perm-eyebrow { margin: 0; color: var(--text-3); font-size: 11px; letter-spacing: .16em; text-transform: uppercase; }
.perm-notice { margin: 0; width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-2); color: var(--text-2); font-size: 14px; line-height: 1.7; }
.perm-spinner {
  width: 22px; height: 22px; border-radius: 50%;
  border: 2px solid var(--overlay-3); border-top-color: var(--accent);
  animation: perm-spin .8s linear infinite;
}
.perm-progress { display: block; width: 100%; height: 3px; margin-top: 4px; border-radius: 99px; background: var(--track); overflow: hidden; }
.perm-progress i { display: block; width: 34%; height: 100%; border-radius: 99px; background: var(--accent); animation: perm-slide 1.4s ease-in-out infinite; }
.perm-steps { display: grid; gap: 14px; width: 100%; margin: 4px 0 0; padding: 0; list-style: none; }
.perm-steps li { display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 12px; align-items: start; }
.perm-num { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: var(--overlay-2); color: var(--text-2); font-size: 12px; font-variant-numeric: tabular-nums; }
.perm-steps strong { display: block; font-size: 15px; line-height: 1.6; }
.perm-steps small { display: block; margin-top: 2px; color: var(--text-3); font-size: 14px; line-height: 1.7; }
.perm-actions { display: flex; justify-content: flex-end; gap: 10px; width: 100%; margin-top: 8px; }
@keyframes perm-spin { to { transform: rotate(360deg); } }
@keyframes perm-slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(320%); } }
@keyframes perm-in { from { opacity: 0; transform: translateY(10px) scale(.98); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) {
  .perm-dialog { animation: none; }
  .perm-spinner { animation: none; border-top-color: var(--accent); }
  .perm-progress i { animation: none; width: 100%; }
}
@media (max-width: 520px) { .perm-body { padding: 22px; } .perm-actions .button { flex: 1; } }
</style>
