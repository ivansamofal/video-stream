<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">Latest Videos</h1>

    <div v-if="loading" class="text-gray-400">Loading…</div>

    <div v-else-if="videos.length === 0" class="text-gray-400">
      No videos yet. <router-link to="/upload" class="text-indigo-400 hover:underline">Upload one!</router-link>
    </div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      <router-link
        v-for="v in videos"
        :key="v.id"
        :to="`/watch/${v.id}`"
        class="bg-gray-900 rounded-lg overflow-hidden hover:ring-2 hover:ring-indigo-500 transition-all"
      >
        <div class="aspect-video bg-gray-800 flex items-center justify-center overflow-hidden">
          <img
            v-if="v.thumbnail_url"
            :src="v.thumbnail_url"
            :alt="v.title"
            class="w-full h-full object-cover"
          />
          <svg v-else class="w-12 h-12 text-gray-600" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z"/>
          </svg>
        </div>
        <div class="p-3">
          <p class="font-medium truncate">{{ v.title }}</p>
          <p class="text-xs text-gray-400 mt-1">{{ formatDuration(v.duration_seconds) }}</p>
        </div>
      </router-link>
    </div>

    <div v-if="total > pageSize" class="flex justify-center gap-4 mt-8">
      <button @click="page--" :disabled="page === 1"
        class="px-4 py-2 bg-gray-800 rounded disabled:opacity-40 hover:bg-gray-700 transition-colors">
        Previous
      </button>
      <span class="py-2 text-gray-400">Page {{ page }}</span>
      <button @click="page++" :disabled="page * pageSize >= total"
        class="px-4 py-2 bg-gray-800 rounded disabled:opacity-40 hover:bg-gray-700 transition-colors">
        Next
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import api from '@/api/client'

interface Video {
  id: number
  title: string
  duration_seconds: number | null
  thumbnail_url: string | null
}

const videos = ref<Video[]>([])
const loading = ref(true)
const page = ref(1)
const total = ref(0)
const pageSize = 20

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/videos/', { params: { page: page.value, page_size: pageSize } })
    videos.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function formatDuration(secs: number | null): string {
  if (!secs) return ''
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

onMounted(load)
watch(page, load)
</script>
