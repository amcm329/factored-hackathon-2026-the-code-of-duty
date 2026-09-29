const api_url = import.meta.env.VITE_API_URL

export async function send_chat(message, language = "en", history = []) {
    const response = await fetch(`${api_url}/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            message,
            language,
            history
        })
    })

    if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`)
    }

    const data = await response.json()

    return data.response
}