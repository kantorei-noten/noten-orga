<script setup>
import { onUnmounted, ref, watch } from 'vue'

const bpm = ref(90)
const beats = ref(4) // Zählzeiten je Takt — auch ungerade (5, 7 …)
const laeuft = ref(false)
const aktiv = ref(-1)

let ctx = null
let timer = null
let position = 0

function klick(betont) {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.frequency.value = betont ? 1320 : 880
  osc.connect(gain)
  gain.connect(ctx.destination)
  const t = ctx.currentTime
  gain.gain.setValueAtTime(0.0001, t)
  gain.gain.exponentialRampToValueAtTime(0.6, t + 0.001)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.05)
  osc.start(t)
  osc.stop(t + 0.06)
}

function tick() {
  const b = position % beats.value
  aktiv.value = b
  klick(b === 0)
  position++
}

function start() {
  ctx = ctx || new (window.AudioContext || window.webkitAudioContext)()
  if (ctx.state === 'suspended') ctx.resume()
  position = 0
  tick()
  timer = setInterval(tick, 60000 / bpm.value)
  laeuft.value = true
}
function stop() {
  clearInterval(timer)
  timer = null
  laeuft.value = false
  aktiv.value = -1
}
function toggle() {
  laeuft.value ? stop() : start()
}

watch(bpm, () => {
  if (laeuft.value) {
    clearInterval(timer)
    timer = setInterval(tick, 60000 / bpm.value)
  }
})

onUnmounted(stop)
</script>

<template>
  <h1>Metronom</h1>
  <div class="card" style="max-width: 460px">
    <div class="beats">
      <span v-for="i in beats" :key="i" class="beat" :class="{ on: aktiv === i - 1, accent: i === 1 }" />
    </div>

    <div class="bpm">{{ bpm }} <span class="muted" style="font-size: 14px">BPM</span></div>
    <input class="range" type="range" min="30" max="240" v-model.number="bpm" />

    <div class="toolbar" style="justify-content: center; margin-top: 12px">
      <span class="muted">Zählzeiten</span>
      <button class="btn sm secondary" @click="beats = Math.max(1, beats - 1)">−</button>
      <b style="min-width: 28px; text-align: center">{{ beats }}</b>
      <button class="btn sm secondary" @click="beats = Math.min(12, beats + 1)">+</button>
      <span class="muted" style="font-size: 12px">(auch ungerade, z. B. 5/8, 7/8)</span>
    </div>

    <button class="btn primary" style="width: 100%; margin-top: 14px" @click="toggle">
      {{ laeuft ? 'Stopp' : 'Start' }}
    </button>
  </div>
</template>

<style scoped>
.beats { display: flex; gap: 8px; justify-content: center; margin-bottom: 16px; min-height: 22px; }
.beat { width: 18px; height: 18px; border-radius: 50%; background: var(--surface-2); border: 1px solid var(--border-strong); transition: transform 80ms, background 80ms; }
.beat.on { background: var(--accent); transform: scale(1.25); }
.beat.accent { border-color: var(--accent); }
.bpm { text-align: center; font-size: 40px; font-weight: 700; font-variant-numeric: tabular-nums; }
.range { width: 100%; }
</style>
