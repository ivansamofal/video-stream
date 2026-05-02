import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api, { setAccessToken } from '@/api/client'

interface User {
  id: number
  email: string
  is_admin: boolean
  created_at: string
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin ?? false)

  async function login(email: string, password: string) {
    const { data } = await api.post('/auth/login', { email, password })
    token.value = data.access_token
    setAccessToken(data.access_token)
    await fetchMe()
  }

  async function register(email: string, password: string) {
    await api.post('/auth/register', { email, password })
    await login(email, password)
  }

  async function fetchMe() {
    const { data } = await api.get('/auth/me')
    user.value = data
  }

  async function logout() {
    await api.post('/auth/logout')
    token.value = null
    user.value = null
    setAccessToken(null)
  }

  async function tryRestoreSession() {
    try {
      const { data } = await api.post('/auth/refresh')
      token.value = data.access_token
      setAccessToken(data.access_token)
      await fetchMe()
    } catch {
      // no valid refresh cookie — user stays logged out
    }
  }

  return { user, token, isLoggedIn, isAdmin, login, register, logout, tryRestoreSession }
})
