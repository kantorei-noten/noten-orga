<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api'

const ROLLEN = ['admin', 'musiker', 'chor', 'gast']
const users = ref([])
const neu = ref({ benutzername: '', passwort: '', rolle: 'chor' })
const angelegt = ref(null)
const fehler = ref('')
const bearb = ref(null) // { id, benutzername, passwort, msg, uri }

async function load() {
  try {
    users.value = await api.get('/benutzer')
  } catch (e) {
    fehler.value = 'Benutzer konnten nicht geladen werden: ' + (e?.message || '')
  }
}

async function anlegen() {
  fehler.value = ''
  angelegt.value = null
  try {
    angelegt.value = await api.post('/benutzer', { ...neu.value })
    neu.value = { benutzername: '', passwort: '', rolle: 'chor' }
    await load()
  } catch (e) {
    fehler.value = e.status === 409 ? 'Benutzername existiert bereits.' : 'Fehler: ' + e.message
  }
}

function bearbeiten(u) {
  bearb.value = bearb.value?.id === u.id ? null : { id: u.id, benutzername: u.benutzername, passwort: '', msg: '', uri: '' }
}

async function nameSpeichern(u) {
  const b = bearb.value
  b.msg = ''
  b.uri = ''
  try {
    await api.patch(`/benutzer/${u.id}`, { benutzername: b.benutzername.trim() })
    b.msg = 'Benutzername gespeichert.'
    await load()
  } catch (e) {
    b.msg = e.status === 409 ? 'Benutzername existiert bereits.' : 'Fehler: ' + e.message
  }
}

async function passwortSetzen(u) {
  const b = bearb.value
  b.msg = ''
  b.uri = ''
  if ((b.passwort || '').length < 8) {
    b.msg = 'Passwort muss mindestens 8 Zeichen haben.'
    return
  }
  try {
    await api.post(`/benutzer/${u.id}/passwort`, { passwort: b.passwort })
    b.passwort = ''
    b.msg = 'Passwort gesetzt. Der Nutzer wurde überall abgemeldet.'
  } catch (e) {
    b.msg = 'Fehler: ' + e.message
  }
}

async function toggle2fa(u) {
  const b = bearb.value
  b.msg = ''
  b.uri = ''
  try {
    const r = await api.post(`/benutzer/${u.id}/2fa`, { aktiv: !u.totp_aktiviert })
    if (r.totp_aktiviert) {
      b.uri = r.totp_uri
      b.msg = '2FA aktiviert – neues Geheimnis dem Nutzer geben (unten).'
    } else {
      b.msg = '2FA deaktiviert.'
    }
    await load()
  } catch (e) {
    b.msg = 'Fehler: ' + e.message
  }
}

async function setzeRolle(u, rolle) {
  fehler.value = ''
  try {
    await api.patch(`/benutzer/${u.id}`, { rolle })
    await load()
  } catch (e) {
    fehler.value = e.message
    await load()
  }
}

async function toggleAktiv(u) {
  fehler.value = ''
  try {
    await api.patch(`/benutzer/${u.id}`, { aktiv: !u.aktiv })
    await load()
  } catch (e) {
    fehler.value = e.message
  }
}

async function loeschen(u) {
  if (!confirm(`Benutzer „${u.benutzername}" wirklich löschen? Das kann nicht rückgängig gemacht werden.`)) return
  fehler.value = ''
  try {
    await api.del(`/benutzer/${u.id}`)
    if (bearb.value?.id === u.id) bearb.value = null
    await load()
  } catch (e) {
    fehler.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <h1>Benutzer</h1>
  <div class="card" style="max-width: 620px; margin-bottom: 18px">
    <b>Neuen Benutzer anlegen</b> <span class="muted">(kein Self-Signup — Konten legt der Admin an)</span>
    <div class="toolbar" style="margin: 10px 0 0; flex-wrap: wrap">
      <input class="input" v-model="neu.benutzername" placeholder="Benutzername" style="max-width: 180px" />
      <input class="input" type="text" v-model="neu.passwort" placeholder="Passwort (min. 8)" style="max-width: 180px" />
      <select class="input" v-model="neu.rolle" style="max-width: 130px">
        <option v-for="r in ROLLEN" :key="r" :value="r">{{ r }}</option>
      </select>
      <button class="btn primary" :disabled="!neu.benutzername || neu.passwort.length < 8" @click="anlegen">Anlegen</button>
    </div>
    <p v-if="fehler" class="error">{{ fehler }}</p>
    <div v-if="angelegt" class="totp-box">
      <b>{{ angelegt.benutzername }}</b> angelegt. 2FA für die Authenticator-App (dem Nutzer geben):
      <code>{{ angelegt.totp_uri }}</code>
    </div>
  </div>

  <div class="stack">
    <div v-for="u in users" :key="u.id" class="ubox">
      <div class="row">
        <div class="main">
          <b>{{ u.benutzername }}</b>
          <div class="sub">
            {{ u.email || '—' }} ·
            <span :class="{ tfa: u.totp_aktiviert }">2FA {{ u.totp_aktiviert ? 'an' : 'aus' }}</span>
          </div>
        </div>
        <select class="input" style="max-width: 120px" :value="u.rolle" @change="setzeRolle(u, $event.target.value)">
          <option v-for="r in ROLLEN" :key="r" :value="r">{{ r }}</option>
        </select>
        <button class="btn sm" :class="u.aktiv ? 'secondary' : 'ghost'" @click="toggleAktiv(u)">
          {{ u.aktiv ? 'aktiv' : 'inaktiv' }}
        </button>
        <button class="btn sm ghost" @click="bearbeiten(u)">Bearbeiten ✎</button>
        <button class="btn sm ghost" title="Benutzer löschen" @click="loeschen(u)">✕</button>
      </div>

      <div v-if="bearb && bearb.id === u.id" class="konfig">
        <div class="feldzeile">
          <label class="kf"><span>Benutzername</span><input class="input" v-model="bearb.benutzername" /></label>
          <button class="btn sm secondary" @click="nameSpeichern(u)">Name speichern</button>
        </div>
        <div class="feldzeile">
          <label class="kf"><span>Neues Passwort</span>
            <input class="input" type="text" v-model="bearb.passwort" placeholder="min. 8 Zeichen" />
          </label>
          <button class="btn sm secondary" @click="passwortSetzen(u)">Passwort setzen</button>
        </div>
        <div class="feldzeile">
          <span class="kf"><span>Zwei-Faktor (2FA)</span><b>{{ u.totp_aktiviert ? 'aktiviert' : 'deaktiviert' }}</b></span>
          <button class="btn sm secondary" @click="toggle2fa(u)">
            {{ u.totp_aktiviert ? '2FA ausschalten' : '2FA einschalten' }}
          </button>
        </div>
        <div v-if="bearb.uri" class="totp-box">
          Neues 2FA-Geheimnis (dem Nutzer für die Authenticator-App geben):
          <code>{{ bearb.uri }}</code>
        </div>
        <p v-if="bearb.msg" class="muted" style="margin: 6px 0 0">{{ bearb.msg }}</p>
        <p class="muted" style="font-size: 12px; margin: 4px 0 0">
          Hinweis: 2FA wirkt beim Login nur, wenn 2FA serverseitig verpflichtend ist. Der letzte aktive Admin ist
          gegen Löschen/Deaktivieren geschützt.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ubox { border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--paper); }
.ubox .row { padding: 8px 10px; }
.tfa { color: var(--success); font-weight: 600; }
.konfig { padding: 10px 12px; border-top: 1px solid var(--border); background: var(--surface); }
.feldzeile { display: flex; align-items: flex-end; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.kf { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--ink-2); }
.kf .input { min-width: 200px; }
.totp-box { background: var(--success-tint); color: var(--success); border-radius: var(--radius-sm); padding: 10px 12px; margin-top: 8px; font-size: var(--text-sm); }
.totp-box code { display: block; margin-top: 4px; word-break: break-all; background: none; border: none; color: var(--ink-2); }
</style>
