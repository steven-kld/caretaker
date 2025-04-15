import { useEffect, useState } from "react"
import { initializeSessionFromURL } from "../api/session"

export default function InterviewPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    initializeSessionFromURL()
      .then(setData)
      .catch(setError)
  }, [])

  if (error) {
    return <div className="text-red-400 text-center mt-10">❌ Failed to load interview</div>
  }

  if (!data) {
    return <div className="text-white text-center mt-10">Loading...</div>
  }

  return (
    <div className="text-white max-w-2xl mx-auto p-6">
      <h1 className="text-3xl font-semibold mb-2">{data.interview_name}</h1>
      <p className="text-gray-300 mb-6">{data.welcome_text}</p>

      {/* Use `data.questions` and `data.respondent_id` later */}
    </div>
  )
}
