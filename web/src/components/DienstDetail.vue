<script setup>
import { ref } from 'vue'

import { api } from '@/api'

const props = defineProps({
  dienst: { type: Object, required: true },
  setlisten: { type: Array, default: () => [] },
  darfSchreiben: { type: Boolean, default: false }
})
const emit = defineEmits(['reload'])

const bearb = ref(false)
const entwurf = ref({})

function starte() {
  entwurf.value = {
    datum: props.dienst.datum || '',
    setliste_id: props.dienst.setliste_id || '',
    notiz: props.dienst.notiz || ''
  }
  bearb.value = true
}
async function speichern() {
  await api.patch(`/dienste/${props.dienst.id}`, {
    datum: entwurf.value.datum || null,
    setliste_id: entwurf.value.setliste_id || null,
    notiz: (entwurf.value.notiz || '').trim() || null
  })
  bearb.value = false
  emit('reload')
}
async function bestaetigen() {
  await api.patch(`/dienste/${props.dienst.id}`, { bestaetigt: !props.dienst.bestaetigt })
  emit('reload')
}
async function loeschen() {
  if (!confirm('Dienst wirklich löschen?')) return
  await api.del(`/dienste/${props.dienst.id}`)
  emit('reload')
}
function sym(s) {
  return s === 'zugesagt' ? '✓' : s === 'abgesagt' ? '✕' : '·'
}
</script>

<template>
  <div class="dd">
    <div class="mitglieder">
      <div v-for="t in dienst.teilnehmer" :key="t.id" class="mrow" :class="t.status">
        <span class="sym">{{ sym(t.status) }}</span>
        <b>{{ t.benutzername }}</b>
        <span class="st">{{ t.status }}</span>
        <span v-if="t.notiz" class="tn">„{{ t.notiz }}"</span>
      </div>
      <div v-if="!(dienst.teilnehmer || []).length" class="muted" style="font-size: var(--text-sm)">Keine Mitglieder in der Gruppe.</div>
    </div>

    <div v-if="darfSchreiben" class="ddtools">
      <template v-if="!bearb">
        <button class="btn sm ghost" @click="starte">Bearbeiten ✎</button>
        <button class="btn sm" :class="dienst.bestaetigt ? 'secondary' : 'ghost'" @click="bestaetigen">
          {{ dienst.bestaetigt ? '✓ bestätigt' : 'als bestätigt markieren' }}
        </button>
        <button class="btn sm ghost" @click="loeschen">Löschen</button>
      </template>
      <template v-else>
        <label class="kf"><span>Datum</span><input class="input" type="date" v-model="entwurf.datum" /></label>
        <label class="kf"><span>Setliste</span>
          <select class="input" v-model="entwurf.setliste_id" style="min-width: 160px">
            <option value="">—</option>
            <option v-for="sl in setlisten" :key="sl.id" :value="sl.id">{{ sl.name }}</option>
          </select>
        </label>
        <label class="kf"><span>Notiz</span><input class="input" v-model="entwurf.notiz" style="min-width: 160px" /></label>
        <button class="btn sm primary" @click="speichern">Speichern</button>
        <button class="btn sm ghost" @click="bearb = false">Abbrechen</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.dd { padding: 8px 4px 2px; }
.mrow { display: flex; align-items: center; gap: 8px; padding: 3px 0; font-size: var(--text-sm); }
.mrow .sym { width: 16px; text-align: center; font-weight: 700; }
.mrow.zugesagt .sym { color: var(--success); }
.mrow.abgesagt .sym { color: var(--danger, #c4463f); }
.mrow .st { color: var(--ink-2); font-size: 12px; }
.mrow .tn { color: var(--ink-2); font-style: italic; }
.ddtools { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; margin-top: 8px; }
.kf { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--ink-2); }
</style>
