<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const totp = ref('')
const totpNoetig = ref(true)
const fehler = ref('')
const busy = ref(false)

onMounted(async () => {
  try {
    totpNoetig.value = (await api.get('/auth/config')).totp_pflicht
  } catch {
    /* im Zweifel 2FA-Feld zeigen */
  }
})

async function anmelden() {
  fehler.value = ''
  busy.value = true
  try {
    await auth.login(username.value, password.value, totp.value)
    router.push(route.query.redirect || { name: 'katalog' })
  } catch (e) {
    fehler.value = e.status === 423 ? 'Konto vorübergehend gesperrt.' : 'Anmeldung fehlgeschlagen.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="card login-card" @submit.prevent="anmelden">
      <div class="logo">
        <svg width="34" height="34" viewBox="0 0 96 96" aria-hidden="true">
          <g fill="var(--accent)">
            <rect x="47" y="21" width="6.5" height="43" rx="3.25" />
            <path d="M53 21c14 1 21 11 18 24-1-11-9-17-18-19z" />
            <ellipse cx="36" cy="66" rx="14" ry="11" transform="rotate(-18 36 66)" />
          </g>
        </svg>
        <b>Kantorei</b>
      </div>
      <p class="muted" style="margin-top: 0">Notenarchiv — bitte anmelden</p>

      <label class="field"><span>Benutzername</span>
        <input class="input" v-model="username" autocomplete="username" autofocus />
      </label>
      <label class="field"><span>Passwort</span>
        <input class="input" type="password" v-model="password" autocomplete="current-password" />
      </label>
      <label v-if="totpNoetig" class="field"><span>2FA-Code (TOTP)</span>
        <input class="input" v-model="totp" inputmode="numeric" autocomplete="one-time-code" placeholder="6-stellig" />
      </label>

      <p v-if="fehler" class="error">{{ fehler }}</p>
      <button class="btn primary" style="width: 100%" :disabled="busy">
        {{ busy ? 'Anmelden …' : 'Anmelden' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-wrap { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.login-card { width: 100%; max-width: 360px; }
.logo { display: flex; align-items: center; gap: 10px; font-size: 22px; margin-bottom: 2px; }
</style>
