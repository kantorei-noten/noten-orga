<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const setlisten = ref([])
const laden = ref(true)
const neuName = ref('')
const neuDatum = ref('')

async function load() {
  try {
    setlisten.value = await api.get('/setlisten')
  } finally {
    laden.value = false
  }
}

async function anlegen() {
  if (!neuName.value.trim()) return
  await api.post('/setlisten', { name: neuName.value.trim(), datum: neuDatum.value || null })
  neuName.value = ''
  neuDatum.value = ''
  await load()
}

onMounted(load)
</script>

<template>
  <h1>Setlisten</h1>

  <div v-if="auth.darfSchreiben" class="card" style="max-width: 560px; margin-bottom: 18px">
    <div class="toolbar" style="margin: 0">
      <input class="input" v-model="neuName" placeholder="Name, z. B. Gottesdienst 1. Advent" @keyup.enter="anlegen" />
      <input class="input" type="date" v-model="neuDatum" style="max-width: 170px" />
      <button class="btn primary" :disabled="!neuName.trim()" @click="anlegen">Anlegen</button>
    </div>
  </div>

  <p v-if="laden" class="muted">Lädt …</p>
  <div v-else-if="setlisten.length === 0" class="empty">Noch keine Setliste angelegt.</div>
  <div v-else class="stack">
    <div v-for="s in setlisten" :key="s.id" class="row">
      <div class="main">
        <b>{{ s.name }}</b>
        <div class="sub">{{ s.datum || 'ohne Datum' }} · {{ s.anzahl_eintraege }} Einträge</div>
      </div>
      <RouterLink class="btn sm secondary" :to="{ name: 'setliste', params: { id: s.id } }">Öffnen</RouterLink>
      <RouterLink class="btn sm primary" :to="{ name: 'spielen', params: { setlisteId: s.id } }">Spielen</RouterLink>
    </div>
  </div>
</template>
