import { defineStore } from 'pinia'

import { api } from '@/api'

export const useAuth = defineStore('auth', {
  state: () => ({ user: null, ready: false }),
  getters: {
    isLoggedIn: (s) => !!s.user,
    rolle: (s) => s.user?.rolle || null,
    istAdmin: (s) => s.user?.rolle === 'admin',
    darfSchreiben: (s) => ['admin', 'musiker'].includes(s.user?.rolle)
  },
  actions: {
    async fetchMe() {
      try {
        this.user = await api.get('/auth/me')
      } catch {
        this.user = null
      } finally {
        this.ready = true
      }
    },
    async login(username, password, totp) {
      await api.post('/auth/login', { username, password, totp })
      await this.fetchMe()
    },
    async logout() {
      try {
        await api.post('/auth/logout')
      } finally {
        this.user = null
      }
    }
  }
})
