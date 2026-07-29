<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppNav from '@/components/AppNav.vue'
import { useOnline } from '@/composables/online'

const route = useRoute()
const online = useOnline()
const chromeless = computed(() => route.meta.public || route.meta.fullscreen)

// AGPL §13: Wer die Anwendung über das Netz nutzt, muss an den Quellcode kommen.
// Forks setzen VITE_QUELLCODE_URL beim Build auf ihr eigenes, geändertes Repository.
const quellcodeUrl = import.meta.env.VITE_QUELLCODE_URL || 'https://github.com/kantorei-noten/noten-orga'
</script>

<template>
  <div v-if="!online && !chromeless" class="offline-banner">
    Offline — gespeicherte Inhalte bleiben verfügbar
  </div>
  <AppNav v-if="!chromeless" />
  <main :class="{ 'with-nav': !chromeless }">
    <RouterView />
  </main>
  <footer v-if="!route.meta.fullscreen" class="app-footer">
    © 2026 by Michael Henseleit ·
    <a :href="quellcodeUrl" target="_blank" rel="noopener noreferrer">Quellcode</a> · AGPL-3.0
  </footer>
</template>

<style scoped>
.offline-banner {
  position: sticky; top: 0; z-index: 30;
  background: var(--warning-tint); color: var(--warning);
  text-align: center; font-size: var(--text-sm); font-weight: var(--fw-medium);
  padding: 6px 12px; border-bottom: 1px solid var(--border);
}
.app-footer {
  text-align: center; color: var(--ink-2); font-size: 12px;
  padding: 18px 12px 24px; margin-top: 8px;
}
.app-footer a { color: inherit; text-decoration: underline; }
.app-footer a:hover { color: var(--accent); }
</style>
