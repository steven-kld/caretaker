export async function initializeSession() {
  try {
    const res = await fetch('/api/session/init', {
      method: 'GET',
      credentials: 'include' // Important: ensures Flask session cookie is stored
    })

    const data = await res.json()
    console.log("📥 Session initialized:", data)
    return data
  } catch (err) {
    console.error("❌ Failed to initialize session:", err)
    throw err
  }
}
