<template>
  <div>
    <h1 class="text-2xl font-bold mb-2">Admin Panel</h1>

    <div class="flex gap-2 mb-6 flex-wrap">
      <button
        v-for="s in statuses"
        :key="s.value"
        @click="filterStatus = s.value"
        :class="[
          'px-3 py-1 rounded text-sm transition-colors',
          filterStatus === s.value
            ? 'bg-indigo-600 text-white'
            : 'bg-gray-800 text-gray-300 hover:bg-gray-700',
        ]"
      >
        {{ s.label }}
      </button>
    </div>

    <div v-if="loading" class="text-gray-400">Loading…</div>

    <div v-else-if="videos.length === 0" class="text-gray-400">No videos.</div>

    <div v-else class="space-y-3">
      <div
        v-for="v in videos"
        :key="v.id"
        class="bg-gray-900 rounded-lg p-4 flex items-center justify-between gap-4"
      >
        <div class="min-w-0">
          <p class="font-medium truncate">{{ v.title }}</p>
          <p class="text-xs text-gray-400 mt-0.5">
            ID {{ v.id }} · {{ v.status }} · {{ new Date(v.created_at).toLocaleString() }}
          </p>
          <p v-if="v.error_message" class="text-xs text-red-400 mt-1 truncate">{{ v.error_message }}</p>
        </div>

        <div class="flex gap-2 shrink-0">
          <button
            v-if="v.status === 'pending_review'"
            @click="approve(v.id)"
            class="px-3 py-1 bg-green-700 hover:bg-green-600 rounded text-sm transition-colors"
          >
            Approve
          </button>
          <button
            v-if="v.status === 'pending_review'"
            @click="reject(v.id)"
            class="px-3 py-1 bg-red-700 hover:bg-red-600 rounded text-sm transition-colors"
          >
            Reject
          </button>
          <router-link
            v-if="v.status === 'published'"
            :to="`/watch/${v.id}`"
            class="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
          >
            Watch
          </router-link>
        </div>
      </div>
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

interface AdminVideo {
  id: number
  title: string
  status: string
  created_at: string
  error_message: string | null
}

const statuses = [
  { label: 'All', value: '' },
  { label: 'Pending Review', value: 'pending_review' },
  { label: 'Published', value: 'published' },
  { label: 'Processing', value: 'processing' },
  { label: 'Rejected', value: 'rejected' },
  { label: 'Failed', value: 'failed' },
]

const videos = ref<AdminVideo[]>([])
const loading = ref(true)
const page = ref(1)
const total = ref(0)
const pageSize = 20
const filterStatus = ref('')

async function load() {
  loading.value = true
  try {
    const params: Record<string, string | number> = { page: page.value, page_size: pageSize }
    if (filterStatus.value) params.status = filterStatus.value
    const { data } = await api.get('/admin/videos', { params })
    videos.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function approve(id: number) {
  await api.patch(`/admin/videos/${id}/approve`)
  load()
}

async function reject(id: number) {
  await api.patch(`/admin/videos/${id}/reject`)
  load()
}

onMounted(load)
watch([page, filterStatus], load)
</script>
