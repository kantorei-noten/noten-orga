<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, default: '' },
  frets: { type: Array, default: () => [] }, // 6 Werte E-A-D-G-H-e; -1=x, 0=leer
  base: { type: Number, default: 1 }
})

const ST = 6
const FR = 5
const W = 48
const padL = 8
const padR = 8
const padT = 15
const padB = 15
const areaH = 46
const H = padT + areaH + padB
const gapX = (W - padL - padR) / (ST - 1)
const gapY = areaH / FR

const xOf = (i) => padL + i * gapX
const yOf = (f) => padT + f * gapY

const saiten = computed(() => Array.from({ length: ST }, (_, i) => xOf(i)))
const buende = computed(() => Array.from({ length: FR + 1 }, (_, f) => yOf(f)))
const nut = computed(() => props.base <= 1)
const marker = computed(() => props.frets.map((v, i) => ({ x: xOf(i), v })))
const punkte = computed(() =>
  props.frets
    .map((v, i) => {
      if (v > 0) {
        const idx = v - (props.base - 1)
        if (idx >= 1 && idx <= FR) return { x: xOf(i), y: yOf(idx) - gapY / 2 }
      }
      return null
    })
    .filter(Boolean)
)
</script>

<template>
  <svg :viewBox="`0 0 ${W} ${H}`" :width="W" :height="H" class="dia">
    <line
      v-for="(y, i) in buende"
      :key="'f' + i"
      :x1="padL"
      :y1="y"
      :x2="W - padR"
      :y2="y"
      :stroke-width="i === 0 && nut ? 2.4 : 0.7"
    />
    <line v-for="(x, i) in saiten" :key="'s' + i" :x1="x" :y1="padT" :x2="x" :y2="padT + areaH" stroke-width="0.7" />
    <template v-for="(mk, i) in marker" :key="'m' + i">
      <text v-if="mk.v === 0" :x="mk.x" :y="padT - 4" text-anchor="middle" class="mk">o</text>
      <text v-else-if="mk.v < 0" :x="mk.x" :y="padT - 4" text-anchor="middle" class="mk">×</text>
    </template>
    <circle v-for="(p, i) in punkte" :key="'p' + i" :cx="p.x" :cy="p.y" r="2.5" class="dot" />
    <text v-if="!nut" :x="padL - 3" :y="padT + gapY - 1" text-anchor="end" class="bf">{{ base }}fr</text>
    <text :x="W / 2" :y="H - 4" text-anchor="middle" class="nm">{{ name }}</text>
  </svg>
</template>

<style scoped>
.dia { display: block; }
.dia line { stroke: var(--ink); }
.dia .dot { fill: var(--accent-strong); }
.dia .mk { font-size: 6px; fill: var(--ink-2); }
.dia .bf { font-size: 5px; fill: var(--ink-2); }
.dia .nm { font-size: 8px; font-weight: 700; fill: var(--ink); }
</style>
