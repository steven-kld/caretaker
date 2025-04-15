export async function initializeSessionFromURL() {
    const url = new URL(window.location.href)
    const i = url.searchParams.get("i")
    const o = url.searchParams.get("o")
    const c = url.searchParams.get("c")
  
    if (!i || !o) {
      throw new Error("Missing interview or organization ID")
    }
  
    const res = await fetch(`/api/session/init?i=${i}&o=${o}&c=${c}`)
    const text = await res.text()
  
    console.log("📥 Raw response from backend:", text)
  
    try {
      return JSON.parse(text)
    } catch (err) {
      console.error("❌ JSON parse error:", err)
      throw err
    }
  }
  