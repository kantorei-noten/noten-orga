<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const sammlungen = ref([])
const arten = ref([])
const laden = ref(true)
const neuName = ref('')
const neuArt = ref('allgemein')

async function load() {
  try {
    sammlungen.value = await api.get('/sammlungen')
  } finally {
    laden.value = false
  }
}

async function ladeArten() {
  try {
    arten.value = await api.get('/sammlung-arten')
    if (!arten.value.some((a) => a.kuerzel === neuArt.value)) {
      neuArt.value = arten.value[0]?.kuerzel || 'allgemein'
    }
  } catch {
    arten.value = []
  }
}

async function anlegen() {
  if (!neuName.value.trim()) return
  await api.post('/sammlungen', { name: neuName.value.trim(), art: neuArt.value })
  neuName.value = ''
  await load()
}

onMounted(() => {
  load()
  ladeArten()
})
</script>

<template>
  <h1>Sammlungen</h1>
  <div v-if="auth.darfSchreiben" class="card" style="max-width: 560px; margin-bottom: 18px">
    <div class="toolbar" style="margin: 0">
      <input class="input" v-model="neuName" placeholder="Name, z. B. Orgel-Repertoire" @keyup.enter="anlegen" />
      <select class="input" v-model="neuArt" style="max-width: 150px">
        <option v-for="a in arten" :key="a.kuerzel" :value="a.kuerzel">{{ a.name }}</option>
      </select>
      <button class="btn primary" :disabled="!neuName.trim()" @click="anlegen">Anlegen</button>
    </div>
  </div>

  <p v-if="laden" class="muted">Lädt …</p>
  <div v-else-if="sammlungen.length === 0" class="empty">Noch keine Sammlung angelegt.</div>
  <div v-else class="stack">
    <RouterLink
      v-for="s in sammlungen"
      :key="s.id"
      class="row"
      :to="{ name: 'sammlung', params: { id: s.id } }"
    >
      <div class="main">
        <b>{{ s.name }}</b>
        <div class="sub"><span class="tag">{{ s.art_name || s.art }}</span> {{ s.anzahl_werke }} Werke</div>
      </div>
    </RouterLink>
  </div>
</template>
