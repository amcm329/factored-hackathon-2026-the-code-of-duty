const api_url = import.meta.env.VITE_API_URL

export async function request_evidence_upload(file) {
    const response = await fetch(`${api_url}/evidence/presign`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            content_type: file.type,
            size: file.size
        })
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

    form_data.append("file", file)

    const response = await fetch(upload.url, {
        method: "POST",
        body: form_data
    })

    if (!response.ok) {
        throw new Error(`S3 upload failed: ${response.status}`)
    }
}

export async function process_evidence(evidence_id, language = "en") {
    const response = await fetch(`${api_url}/evidence/process`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            evidence_id,
            language
        })
    })

    if (!response.ok) {
        throw new Error(`Evidence processing failed: ${response.status}`)
    }

    return response.json()
}

export async function send_chat(message, language = "en", history = [], evidence_ids = []) {
    const response = await fetch(`${api_url}/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            message,
            language,
            history,
            evidence_ids
        })
    })

    if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`)
    }

    const data = await response.json()

    return data.response
}