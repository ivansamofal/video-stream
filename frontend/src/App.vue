<template>
  <div class="min-h-screen bg-gray-950 text-gray-100">
    <nav class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
      <router-link to="/" class="text-xl font-bold text-indigo-400">VideoStream</router-link>
      <div class="flex items-center gap-4 text-sm">
        <template v-if="auth.isLoggedIn">
          <router-link to="/upload" class="hover:text-indigo-400 transition-colors">Upload</router-link>
          <router-link v-if="auth.isAdmin" to="/admin" class="hover:text-indigo-400 transition-colors">Admin</router-link>
          <span class="text-gray-400">{{ auth.user?.email }}</span>
          <button @click="handleLogout" class="text-red-400 hover:text-red-300 transition-colors">Logout</button>
        </template>
        <template v-else>
          <router-link to="/login" class="hover:text-indigo-400 transition-colors">Login</router-link>
          <router-link to="/register" class="bg-indigo-600 hover:bg-indigo-500 px-3 py-1 rounded transition-colors">Register</router-link>
        </template>
      </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 py-8">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

onMounted(() => auth.tryRestoreSession())

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>
