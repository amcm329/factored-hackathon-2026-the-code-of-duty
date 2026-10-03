import { get_id_token } from './auth'

const api_url = import.meta.env.VITE_API_URL

function auth_headers(include_json = true) {
  const headers = {}

  if (include_json) {
    headers['Content-Type'] = 'application/json'
  }

  const token = get_id_token()

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  return headers
}

export async function get_welcome_message(language = 'en') {
  const response = await fetch(`${api_url}/messages/welcome?language=${encodeURIComponent(language)}`)

  if (!response.ok) {
    throw new Error(`Welcome message request failed: ${response.status}`)
  }

  return response.json()
}

export async function request_evidence_upload(file) {
  const response = await fetch(`${api_url}/evidence/presign`, {
    method: 'POST',
    headers: auth_headers(),
    body: JSON.stringify({
      content_type: file.type,
      size: file.size,
    }),
  })

  if (!response.ok) {
    throw new Error(`Presign request failed: ${response.status}`)
  }

  return response.json()
}

export async function upload_evidence_pdf(file, upload) {
  const form_data = new FormData()

  Object.entries(upload.fields).forEach(([key, value]) => {
    form_data.append(key, value)
  })
  form_data.append('file', file)

  const response = await fetch(upload.url, {
    method: 'POST',
    body: form_data,
  })

  if (!response.ok) {
    throw new Error(`S3 upload failed: ${response.status}`)
  }
}

export async function process_evidence(evidence_id, language = 'en') {
  const response = await fetch(`${api_url}/evidence/process`, {
    method: 'POST',
    headers: auth_headers(),
    body: JSON.stringify({
      evidence_id,
      language,
    }),
  })

  if (!response.ok) {
    throw new Error(`Evidence processing failed: ${response.status}`)
  }

  return response.json()
}

export async function send_chat(message, language = 'en', history = [], evidence_ids = [], interaction_id = '') {
  const response = await fetch(`${api_url}/chat`, {
    method: 'POST',
    headers: auth_headers(),
    body: JSON.stringify({
      message,
      language,
      history,
      evidence_ids,
      interaction_id,
    }),
  })

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`)
  }

  return response.json()
}

export async function list_transactions() {
  const response = await fetch(`${api_url}/transactions`, {
    method: 'GET',
    headers: auth_headers(false),
  })

  if (!response.ok) {
    throw new Error(`Transaction request failed: ${response.status}`)
  }

  return response.json()
}

export async function create_dispute(payload) {
  const response = await fetch(`${api_url}/disputes`, {
    method: 'POST',
    headers: auth_headers(),
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Dispute creation failed: ${response.status}`)
  }

  return response.json()
}
