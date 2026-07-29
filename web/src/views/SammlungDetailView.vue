<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const id = route.params.id
const s = ref(null)
const laden = ref(true)
const suche = ref('')
const treffer = ref([])

const arten = ref([])
const bearb = ref(false)
const entwurf = ref({ name: '', art: '' })

async function load() {
  try {
    s.value = await api.get(`/sammlungen/${id}`)
  } catch {
    s.value = null
  } finally {
    laden.value = false
  }
}
async function ladeArten() {
  try {
    arten.value = await api.get('/sammlung-arten')
  } catch {
    arten.value = []
  }
}

function bearbeiten() {
  entwurf.value = { name: s.value.name, art: s.value.art }
  bearb.value = true
}
async function speichern() {
  try {
    s.value = await api.patch(`/sammlungen/${id}`, { name: entwurf.value.name.trim(), art: entwurf.value.art })
    bearb.value = false
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}
async function loeschen() {
  if (!confirm(`Sammlung „${s.value.name}" wirklich löschen?`)) return
  try {
    await api.del(`/sammlungen/${id}`)
    router.push('/sammlungen')
  } catch (e) {
    alert('Fehler: ' + e.message)
  }
}

async function werkSuchen() {
  if (!suche.value.trim()) {
    treffer.value = []
    return
  }
  const d = await api.get('/suche?q=' + encodeURIComponent(suche.value.trim()))
  treffer.value = d.ergebnisse.slice(0, 6)
}
async function hinzufuegen(w) {
  await api.post(`/sammlungen/${id}/werke`, { werk_id: w.id })
  suche.value = ''
  treffer.value = []
  await load()
}
async function entfernen(werkId) {
  await api.del(`/sammlungen/${id}/werke/${werkId}`)
  await load()
}

onMounted(() => {
  load()
  ladeArten()
})
</script>

<template>
  <p v-if="laden" class="muted">Lädt …</p>
  <template v-else-if="s">
    <RouterLink to="/sammlungen" class="muted" style="font-size: var(--text-sm)">← Sammlungen</RouterLink>
    <div class="toolbar" style="margin: 8px 0 2px">
      <h1 style="margin: 0; flex: 1">{{ s.name }}</h1>
      <template v-if="auth.darfSchreiben">
        <button class="btn sm ghost" @click="bearbeiten">Bearbeiten ✎</button>
        <button class="btn sm ghost" @click="loeschen">Löschen</button>
      </template>
    </div>
    <p class="muted"><span class="tag">{{ s.art_name || s.art }}</span></p>

    <div v-if="bearb" class="card" style="max-width: 560px; margin-bottom: 12px">
      <div class="toolbar" style="margin: 0; flex-wrap: wrap; gap: 8px; align-items: flex-end">
        <label class="kf"><span>Name</span><input class="input" v-model="entwurf.name" /></label>
        <label class="kf"><span>Art</span>
          <select class="input" v-model="entwurf.art">
            <option v-for="a in arten" :key="a.kuerzel" :value="a.kuerzel">{{ a.name }}</option>
          </select>
        </label>
        <button class="btn sm primary" @click="speichern">Speichern</button>
        <button class="btn sm ghost" @click="bearb = false">Abbrechen</button>
      </div>
    </div>

    <div v-if="s.werke.length === 0" class="empty" style="margin: 14px 0">Noch keine Werke.</div>
    <div v-else class="stack" style="margin: 14px 0">
      <div v-for="w in s.werke" :key="w.id" class="row">
        <RouterLink class="main" :to="{ name: 'werk', params: { id: w.id } }" style="text-decoration: none; color: inherit">
          <b>{{ w.titel }}</b>
          <div class="sub">{{ w.komponist || '—' }}</div>
        </RouterLink>
        <button v-if="auth.darfSchreiben" class="btn sm ghost" @click="entfernen(w.id)">✕</button>
      </div>
    </div>

    <div v-if="auth.darfSchreiben" class="card" style="max-width: 560px">
      <b>Werk hinzufügen</b>
      <div class="toolbar" style="margin: 10px 0 0">
        <input class="input" v-model="suche" placeholder="Werk suchen …" @keyup.enter="werkSuchen" />
        <button class="btn secondary" @click="werkSuchen">Suchen</button>
      </div>
      <div class="stack" style="margin-top: 8px">
        <button v-for="w in treffer" :key="w.id" class="row" style="cursor: pointer; text-align: left" @click="hinzufuegen(w)">
          <div class="main"><b>{{ w.titel }}</b><div class="sub">{{ w.komponist || '—' }}</div></div>
          <span style="color: var(--accent); font-size: 20px">+</span>
        </button>
      </div>
    </div>
  </template>
  <div v-else class="empty">Sammlung nicht gefunden.</div>
</template>

<style scoped>
.kf { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--ink-2); }
.kf .input { min-width: 160px; }
</style>
