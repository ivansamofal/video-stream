<template>
  <div class="max-w-xl mx-auto">
    <h1 class="text-2xl font-bold mb-6">Upload Video</h1>

    <form @submit.prevent="submit" class="space-y-5">
      <div>
        <label class="block text-sm text-gray-400 mb-1">Title</label>
        <input v-model="title" type="text" required maxlength="255"
          class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:outline-none focus:border-indigo-500" />
      </div>

      <div>
        <label class="block text-sm text-gray-400 mb-1">Description</label>
        <textarea v-model="description" rows="3"
          class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 focus:outline-none focus:border-indigo-500" />
      </div>

      <div
        @dragover.prevent
        @drop.prevent="onDrop"
        @click="fileInput?.click()"
        class="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center cursor-pointer hover:border-indigo-500 transition-colors"
        :class="{ 'border-indigo-500 bg-indigo-950/20': dragging }"
        @dragenter="dragging = true"
        @dragleave="dragging = false"
      >
        <input ref="fileInput" type="file" accept="video/*" class="hidden" @change="onFileChange" />
        <p v-if="!file" class="text-gray-400">Drag & drop a video file or click to browse</p>
        <p v-else class="text-indigo-400 font-medium">{{ file.name }} ({{ formatBytes(file.size) }})</p>
      </div>

      <div v-if="uploading" class="space-y-1">
        <div class="flex justify-between text-sm text-gray-400">
          <span>Uploading…</span>
          <span>{{ progress }}%</span>
        </div>
        <div class="w-full bg-gray-800 rounded-full h-2">
          <div class="bg-indigo-500 h-2 rounded-full transition-all" :style="{ width: progress + '%' }" />
        </div>
      </div>

      <div v-if="successMsg" class="text-green-400 text-sm">{{ successMsg }}</div>
      <div v-if="error" class="text-red-400 text-sm">{{ error }}</div>

      <button type="submit" :disabled="!file || !title || uploading"
        class="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 py-2 rounded font-medium transition-colors">
        {{ uploading ? 'Uploading…' : 'Upload' }}
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import api from '@/api/client'

const title = ref('')
const description = ref('')
const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const uploading = ref(false)
const progress = ref(0)
const error = ref('')
const successMsg = ref('')

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) file.value = input.files[0]
}

function onDrop(e: DragEvent) {
  dragging.value = false
  const dropped = e.dataTransfer?.files[0]
  if (dropped?.type.startsWith('video/')) file.value = dropped
}

function formatBytes(n: number): string {
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  if (n < 1024 ** 3) return (n / 1024 ** 2).toFixed(1) + ' MB'
  return (n / 1024 ** 3).toFixed(2) + ' GB'
}

async function submit() {
  if (!file.value) return
  error.value = ''
  successMsg.value = ''
  uploading.value = true
  progress.value = 0

  try {
    // Step 1: create the DB record and get a presigned PUT URL
    const { data: init } = await api.post('/videos/initiate-upload', {
      title: title.value,
      description: description.value,
      filename: file.value.name,
      content_type: file.value.type,
    })

    // Step 2: upload the file directly to MinIO — never touches the API server
    await axios.put(init.upload_url, file.value, {
      headers: { 'Content-Type': file.value.type },
      onUploadProgress: (e) => {
        if (e.total) progress.value = Math.round((e.loaded / e.total) * 100)
      },
    })

    // Step 3: tell the API the upload finished so it can queue transcoding
    await api.post(`/videos/${init.video_id}/confirm`)

    successMsg.value = 'Uploaded! Your video is being processed.'
    title.value = ''
    description.value = ''
    file.value = null
    progress.value = 0
  } catch (e: any) {
    error.value = e.response?.data?.detail ?? 'Upload failed'
  } finally {
    uploading.value = false
  }
}
</script>
