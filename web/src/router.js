import { createRouter, createWebHistory } from 'vue-router'

import { useAuth } from '@/stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/', name: 'katalog', component: () => import('@/views/CatalogView.vue') },
  { path: '/suche', name: 'suche', component: () => import('@/views/SearchView.vue') },
  { path: '/erfassen', name: 'erfassen', component: () => import('@/views/ErfassenView.vue') },
  { path: '/werk/:id', name: 'werk', component: () => import('@/views/WerkView.vue') },
  { path: '/noten/:dateiId', name: 'noten', component: () => import('@/views/NotenView.vue') },
  {
    path: '/ansehen',
    name: 'ansehen',
    component: () => import('@/views/AnsehenView.vue'),
    meta: { fullscreen: true }
  },
  {
    path: '/notizblatt',
    name: 'notizblatt',
    component: () => import('@/views/AnnotiertView.vue'),
    meta: { fullscreen: true }
  },
  {
    path: '/notizen',
    name: 'notizen',
    component: () => import('@/views/AnnotationEditorView.vue'),
    meta: { fullscreen: true }
  },
  { path: '/setlisten', name: 'setlisten', component: () => import('@/views/SetlistenView.vue') },
  { path: '/setliste/:id', name: 'setliste', component: () => import('@/views/SetlisteDetailView.vue') },
  { path: '/sammlungen', name: 'sammlungen', component: () => import('@/views/SammlungenView.vue') },
  { path: '/sammlung/:id', name: 'sammlung', component: () => import('@/views/SammlungDetailView.vue') },
  { path: '/dienste', name: 'dienste', component: () => import('@/views/DiensteView.vue') },
  { path: '/chordpro', name: 'chordpro', component: () => import('@/views/ChordProView.vue') },
  { path: '/metronom', name: 'metronom', component: () => import('@/views/MetronomView.vue') },
  { path: '/hilfe', name: 'hilfe', component: () => import('@/views/HelpView.vue') },
  { path: '/einstellungen', name: 'einstellungen', component: () => import('@/views/EinstellungenView.vue') },
  { path: '/benutzer', name: 'benutzer', component: () => import('@/views/BenutzerView.vue') },
  {
    path: '/spielen/:setlisteId?',
    name: 'spielen',
    component: () => import('@/views/SpielmodusView.vue'),
    meta: { fullscreen: true }
  },
  {
    path: '/projektion/:setlisteId',
    name: 'projektion',
    component: () => import('@/views/ProjektionView.vue'),
    meta: { fullscreen: true }
  }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.ready) await auth.fetchMe()
  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.isLoggedIn) return { name: 'katalog' }
})

export default router
