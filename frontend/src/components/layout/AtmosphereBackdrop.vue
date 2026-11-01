<template>
  <div class="atmos" :class="`is-${variant}`" aria-hidden="true">
    <span class="stars" />
    <span class="glow" />
    <span class="water" />
    <span v-if="word" class="word">{{ word }}</span>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ word?: string; variant?: 'page' | 'panel' | 'app' }>(), { word: '', variant: 'page' })
</script>

<style scoped>
.atmos {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
  background:
    linear-gradient(180deg,
      #05060f 0%, #0a0a24 16%, #16113f 30%,
      #2a1a5c 42%, #4a2470 52%, #7a3080 58%,
      #b8487f 61.6%, #ffb3c8 63%, #7a2f6a 66%,
      #3a1a4e 74%, #1c1030 86%, #120b22 100%);
}

.stars {
  position: absolute;
  inset: 0 0 40% 0;
  opacity: .85;
  background-image:
    radial-gradient(1.6px 1.6px at 8% 26%, #fff, transparent),
    radial-gradient(1.1px 1.1px at 16% 14%, rgba(255,255,255,.82), transparent),
    radial-gradient(1.9px 1.9px at 23% 40%, #fff, transparent),
    radial-gradient(1px 1px at 31% 9%, rgba(255,255,255,.7), transparent),
    radial-gradient(1.4px 1.4px at 39% 30%, #fff, transparent),
    radial-gradient(1.1px 1.1px at 46% 17%, rgba(255,255,255,.75), transparent),
    radial-gradient(2px 2px at 53% 6%, #fff, transparent),
    radial-gradient(1px 1px at 61% 33%, rgba(255,255,255,.6), transparent),
    radial-gradient(1.5px 1.5px at 69% 12%, #fff, transparent),
    radial-gradient(1.2px 1.2px at 76% 27%, rgba(255,255,255,.7), transparent),
    radial-gradient(1.8px 1.8px at 84% 8%, #fff, transparent),
    radial-gradient(1px 1px at 91% 22%, rgba(255,255,255,.65), transparent),
    radial-gradient(1.3px 1.3px at 95% 38%, rgba(255,255,255,.5), transparent);
}

.glow {
  position: absolute;
  left: 0; right: 0; top: 55%;
  height: 14%;
  opacity: .9;
  filter: blur(16px);
  background:
    radial-gradient(52% 100% at 50% 62%, rgba(255, 226, 214, .95) 0%, rgba(255, 170, 190, .55) 24%, rgba(190, 90, 150, 0) 62%),
    radial-gradient(90% 60% at 50% 70%, rgba(255, 150, 190, .28) 0%, rgba(80, 30, 90, 0) 70%);
}

.water {
  position: absolute;
  left: 0; right: 0; top: 63%; bottom: 0;
  background:
    repeating-linear-gradient(180deg,
      rgba(255, 214, 230, .16) 0px, rgba(255, 214, 230, .16) 1px,
      transparent 1px, transparent 7px),
    radial-gradient(26% 120% at 50% 0%, rgba(255, 196, 216, .3) 0%, rgba(255, 196, 216, 0) 70%),
    radial-gradient(70% 90% at 50% 4%, rgba(255, 178, 205, .22) 0%, rgba(255, 178, 205, 0) 60%),
    linear-gradient(180deg, rgba(60, 26, 74, .55) 0%, rgba(18, 11, 34, .95) 70%);
  -webkit-mask-image: linear-gradient(180deg, transparent 0%, #000 18%, #000 100%);
  mask-image: linear-gradient(180deg, transparent 0%, #000 18%, #000 100%);
}

.word {
  position: absolute;
  right: -18px;
  top: 12%;
  color: rgba(255, 255, 255, .05);
  font-size: 200px;
  font-weight: 900;
  line-height: .84;
  letter-spacing: .06em;
  user-select: none;
}

/* 面板变体：只保留天空与地平线，用在页面里的 hero 区块 */
.atmos.is-panel {
  background:
    radial-gradient(70% 90% at 78% 118%, rgba(255, 186, 214, .85) 0%, rgba(226, 120, 170, .35) 22%, rgba(80, 30, 100, 0) 56%),
    linear-gradient(180deg, #07071c 0%, #100e38 36%, #24154f 58%, #3d1e60 76%, #55286a 90%, #653370 100%);
}
.atmos.is-panel .glow { top: auto; bottom: -22%; height: 52%; opacity: .8; filter: blur(22px); }
.atmos.is-panel .water { display: none; }
.atmos.is-panel .stars { inset: 0; opacity: .8; }
.atmos.is-panel .word { font-size: 150px; top: 8%; right: 2%; }

/* 应用变体：顶部两团柔光，没有地平线接缝 */
.atmos.is-app {
  background:
    linear-gradient(180deg,
      rgba(8, 7, 15, .96) 0%,
      rgba(13, 10, 32, .93) 14%,
      rgba(26, 17, 58, .86) 26%,
      rgba(42, 23, 74, .78) 38%,
      rgba(58, 28, 86, .68) 47%,
      rgba(74, 34, 92, .6) 53%,
      rgba(86, 38, 96, .55) 57%,
      rgba(48, 23, 60, .72) 67%,
      rgba(22, 14, 34, .9) 82%,
      rgb(9, 8, 15) 100%),
    radial-gradient(70% 34% at 86% -14%, rgba(201, 138, 86, .14) 0%, rgba(9, 8, 16, 0) 66%),
    radial-gradient(60% 30% at 4% -12%, rgba(126, 84, 196, .18) 0%, rgba(9, 8, 16, 0) 70%),
    linear-gradient(180deg, #07060d 0%, #08070f 70%, #0a0813 100%);
}
.atmos.is-app .stars { inset: 0 0 66% 0; opacity: .3; }
.atmos.is-app .glow {
  display: block;
  position: absolute;
  left: 0; right: 0; top: 50%; bottom: auto;
  height: 13%;
  opacity: .45;
  filter: blur(56px);
  background:
    radial-gradient(44% 100% at 50% 50%, rgba(255, 170, 205, .3) 0%, rgba(150, 60, 140, .18) 46%, rgba(60, 24, 70, 0) 78%);
}
.atmos.is-app .water, .atmos.is-app .word { display: none; }
</style>
