<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()
const theme = ref(document.documentElement.dataset.theme || 'light')

function setTheme(t) {
  theme.value = t
  document.documentElement.dataset.theme = t
  try {
    localStorage.setItem('kantorei-theme', t)
  } catch {
    /* ignore */
  }
}

async function abmelden() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <nav class="nav">
    <RouterLink to="/" class="brand">
      <svg width="26" height="26" viewBox="0 0 96 96" aria-hidden="true">
        <g fill="var(--accent)">
          <rect x="47" y="21" width="6.5" height="43" rx="3.25" />
          <path d="M53 21c14 1 21 11 18 24-1-11-9-17-18-19z" />
          <ellipse cx="36" cy="66" rx="14" ry="11" transform="rotate(-18 36 66)" />
        </g>
      </svg>
      Kantorei
    </RouterLink>
    <RouterLink class="link" to="/">Katalog</RouterLink>
    <RouterLink class="link" to="/suche">Suche</RouterLink>
    <RouterLink class="link" to="/setlisten">Setlisten</RouterLink>
    <RouterLink class="link" to="/sammlungen">Sammlungen</RouterLink>
    <RouterLink class="link" to="/dienste">Dienste</RouterLink>
    <RouterLink class="link" to="/chordpro">ChordPro</RouterLink>
    <RouterLink class="link" to="/metronom">Metronom</RouterLink>
    <RouterLink v-if="auth.istAdmin" class="link" to="/benutzer">Benutzer</RouterLink>
    <span class="spacer" />
    <RouterLink class="link" to="/hilfe" title="Anleitung">Hilfe</RouterLink>
    <RouterLink class="link" to="/einstellungen">Einstellungen</RouterLink>
    <div class="seg" role="group" aria-label="Ansicht">
      <button :class="{ active: theme === 'light' }" @click="setTheme('light')">Hell</button>
      <button :class="{ active: theme === 'dark' }" @click="setTheme('dark')">Empore</button>
      <button :class="{ active: theme === 'rot' }" @click="setTheme('rot')">Rot</button>
    </div>
    <span class="who">{{ auth.user?.benutzername }}</span>
    <button class="btn sm secondary" @click="abmelden">Abmelden</button>
  </nav>
</template>
