import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from '@/App.vue'
import router from '@/router'

import '@brand/tokens.css'
import '@/styles/app.css'

// Gespeichertes Theme (Hell / Empore-Dunkel / Rotlicht) früh anwenden
try {
  const t = localStorage.getItem('kantorei-theme')
  if (t) document.documentElement.dataset.theme = t
} catch {
  /* ignore */
}

createApp(App).use(createPinia()).use(router).mount('#app')
