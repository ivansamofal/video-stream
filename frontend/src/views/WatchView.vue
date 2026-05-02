<template>
  <div class="max-w-4xl mx-auto">
    <div v-if="loading" class="text-gray-400">Loading…</div>
    <div v-else-if="!video" class="text-red-400">Video not found.</div>
    <template v-else>
      <div class="aspect-video bg-black rounded-lg overflow-hidden mb-4">
        <video ref="videoEl" class="w-full h-full" controls />
      </div>
      <div class="flex items-start justify-between gap-4 mt-1">
        <h1 class="text-2xl font-bold">{{ video.title }}</h1>
        <button
          v-if="canDelete"
          @click="handleDelete"
          :disabled="deleting"
          class="shrink-0 px-3 py-1 bg-red-700 hover:bg-red-600 disabled:opacity-50 rounded text-sm transition-colors"
        >
          {{ deleting ? 'Deleting…' : 'Delete' }}
        </button>
      </div>
      <p v-if="video.description" class="text-gray-400 mt-2">{{ video.description }}</p>
      <p class="text-xs text-gray-500 mt-2">
        {{ video.duration_seconds ? formatDuration(video.duration_seconds) : '' }}
        · Published {{ video.published_at ? new Date(video.published_at).toLocaleDateString() : '' }}
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Hls from 'hls.js'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'

interface Video {
  id: number
  title: string
  description: string | null
  duration_seconds: number | null
  published_at: string | null
  master_playlist_url: string | null
  owner_id: number
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const video = ref<Video | null>(null)
const loading = ref(true)
const deleting = ref(false)
const videoEl = ref<HTMLVideoElement | null>(null)
let hls: Hls | null = null

const canDelete = computed(() =>
  auth.isLoggedIn && video.value !== null &&
  (auth.user?.id === video.value.owner_id || auth.isAdmin)
)

onMounted(async () => {
  try {
    const { data } = await api.get(`/videos/${route.params.id}`)
    video.value = data
    loading.value = false
    await nextTick()
    initPlayer(data.master_playlist_url)
  } catch {
    loading.value = false
  }
})

onBeforeUnmount(() => hls?.destroy())

async function handleDelete() {
  if (!video.value || !confirm(`Delete "${video.value.title}"?`)) return
  deleting.value = true
  try {
    await api.delete(`/videos/${video.value.id}`)
    router.push('/')
  } finally {
    deleting.value = false
  }
}

function initPlayer(url: string | null) {
  if (!url || !videoEl.value) return
  if (Hls.isSupported()) {
    hls = new Hls()
    hls.loadSource(url)
    hls.attachMedia(videoEl.value)
  } else if (videoEl.value.canPlayType('application/vnd.apple.mpegurl')) {
    videoEl.value.src = url
  }
}

function formatDuration(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>
