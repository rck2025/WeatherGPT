const API_URL = 'http://127.0.0.1:8000/chat'

export async function sendChatMessage(query, location = null, language = 'en') {
  const payload = {
    query,
    language,
    channel: 'web',
  }

  if (location) {
    payload.location = location
  }

  const response = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(`Backend error: ${response.status}`)
  }

  return response.json()
}