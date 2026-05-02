<template>
  <div class="max-w-md mx-auto mt-16">
    <h1 class="text-2xl font-bold mb-6">Create Account</h1>
    <form @submit.prevent="submit" class="space-y-4">
      <div>
        <label class="block text-sm text-gray-400 mb-1">Email</label>
        <input v-model="email" type="email" required
          class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:outline-none focus:border-indigo-500" />
      </div>
      <div>
        <label class="block text-sm text-gray-400 mb-1">Password</label>
        <input v-model="password" type="password" minlength="8" required
          class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:outline-none focus:border-indigo-500" />
      </div>
      <p v-if="error" class="text-red-400 text-sm">{{ error }}</p>
      <button type="submit" :disabled="loading"
        class="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 py-2 rounded font-medium transition-colors">
        {{ loading ? 'Creating…' : 'Create Account' }}
      </button>
    </form>
    <p class="mt-4 text-sm text-gray-400 text-center">
      Already have an account? <router-link to="/login" class="text-indigo-400 hover:underline">Sign in</router-link>
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.register(email.value, password.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? 'Registration failed'
  } finally {
    loading.value = false
  }
}
</script>
