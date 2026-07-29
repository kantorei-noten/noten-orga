<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api'

const props = defineProps({
  titel: { type: String, required: true },
  endpoint: { type: String, required: true }, // z. B. '/besetzungen'
  hatKuerzel: { type: Boolean, default: false },
  hinweis: { type: String, default: '' }
})

const items = ref([])
const neu = ref({ kuerzel: '', name: '', sortierung: 0 })
const msg = ref('')

function key(it) {
  return props.hatKuerzel ? it.kuerzel : it.id
}

async function load() {
  try {
    items.value = await api.get(props.endpoint)
  } catch (e) {
    msg.value = 'Laden fehlgeschlagen: ' + (e?.message || '')
  }
}

async function hinzufuegen() {
  msg.value = ''
  const body = { name: (neu.value.name || '').trim(), sortierung: Number(neu.value.sortierung) || 0 }
  if (props.hatKuerzel) body.kuerzel = (neu.value.kuerzel || '').trim()
  if (!body.name || (props.hatKuerzel && !body.kuerzel)) {
    msg.value = props.hatKuerzel ? 'Bitte Kürzel und Bezeichnung angeben.' : 'Bitte Bezeichnung angeben.'
    return
  }
  try {
    await api.post(props.endpoint, body)
    neu.value = { kuerzel: '', name: '', sortierung: 0 }
    await load()
  } catch (e) {
    msg.value = e.status === 409 ? 'Kürzel existiert bereits.' : 'Fehler: ' + e.message
  }
}

async function speichern(it) {
  msg.value = ''
  try {
    await api.patch(`${props.endpoint}/${key(it)}`, { name: it.name, sortierung: Number(it.sortierung) || 0 })
    msg.value = 'Gespeichert.'
    await load()
  } catch (e) {
    msg.value = 'Fehler: ' + e.message
  }
}

async function loeschen(it) {
  if (!confirm(`„${it.name}" löschen?`)) return
  msg.value = ''
  try {
    await api.del(`${props.endpoint}/${key(it)}`)
    await load()
  } catch (e) {
    msg.value = e.status === 409 ? e.message : 'Fehler: ' + e.message
  }
}

onMounted(load)
</script>

<template>
  <div class="card" style="margin-bottom: 14px">
    <b>{{ titel }}</b>
    <p v-if="hinweis" class="muted" style="font-size: 12px; margin: 4px 0 0">{{ hinweis }}</p>

    <div style="margin-top: 10px">
      <div v-for="it in items" :key="key(it)" class="zeile">
        <span v-if="hatKuerzel" class="tag" style="min-width: 64px; text-align: center">{{ it.kuerzel }}</span>
        <input class="input" v-model="it.name" style="flex: 1; min-width: 120px" />
        <input class="input" type="number" v-model="it.sortierung" title="Reihenfolge" style="width: 72px" />
        <button class="btn sm secondary" title="speichern" @click="speichern(it)">✓</button>
        <button class="btn sm ghost" title="löschen" @click="loeschen(it)">✕</button>
      </div>
    </div>

    <div class="zeile neu">
      <input v-if="hatKuerzel" class="input" v-model="neu.kuerzel" placeholder="Kürzel" style="width: 100px" />
      <input class="input" v-model="neu.name" placeholder="Bezeichnung" style="flex: 1; min-width: 120px" @keyup.enter="hinzufuegen" />
      <input class="input" type="number" v-model="neu.sortierung" title="Reihenfolge" style="width: 72px" />
      <button class="btn sm primary" @click="hinzufuegen">Hinzufügen</button>
    </div>
    <p v-if="msg" class="muted" style="margin: 8px 0 0">{{ msg }}</p>
  </div>
</template>

<style scoped>
.zeile { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.zeile.neu { margin-top: 10px; border-top: 1px solid var(--border); padding-top: 10px; }
</style>
