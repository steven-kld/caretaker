import React, { useState } from 'react'
import RecordRTC from 'recordrtc'
import Heading from './Heading'
import Subtext from './Subtext'
import MainButton from './MainButton'

export default function MainCard({ title, subtitle, buttonText, onAction, children }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [volumeReady, setVolumeReady] = useState(false)

  const handleClick = async () => {
    setError(null)
    setLoading(true)

    try {
      // Request screen + mic
      const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true })
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // Record 2s of mic
      const recorder = new RecordRTC(audioStream, {
        type: 'audio',
        mimeType: 'audio/wav',
        timeSlice: 1000,
        disableLogs: true
      })

      recorder.startRecording()
      await new Promise(resolve => setTimeout(resolve, 2000))

      recorder.stopRecording(async () => {
        const blob = recorder.getBlob()
        const arrayBuffer = await blob.arrayBuffer()
        const audioCtx = new AudioContext()
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer)

        const raw = audioBuffer.getChannelData(0)
        const max = Math.max(...raw.map(Math.abs))

        if (max < 0.01) {
          setError('Microphone seems silent. Try again and speak louder.')
          setLoading(false)
          return
        }

        setVolumeReady(true)
        setTimeout(() => {
          onAction({ screenStream, audioStream })
        }, 500)
      })
    } catch (err) {
      console.error(err)
      setError('Access denied or unavailable. Please allow mic & screen.')
      setLoading(false)
    }
  }

  return (
    <div className="flex z-10 w-full max-w-5xl rounded-3xl bg-white shadow-xl overflow-hidden animate-fadeInUp">
      {/* Left section */}
      <div className="flex-1 p-10 flex flex-col justify-between">
        <div className="mb-6">
          <Heading>{title}</Heading>
          <Subtext>{subtitle}</Subtext>
        </div>

        <div className="space-y-6">
          {children}

          {error && <p className="text-red-500 text-sm">{error}</p>}
          {volumeReady && <p className="text-green-600 text-sm">Ready to go!</p>}

          <MainButton onClick={handleClick}>
            {loading ? 'Sound check…' : buttonText}
          </MainButton>
        </div>
      </div>

      {/* Right image section */}
      <div className="w-2/5 hidden md:block">
        <img
          src="/images/calling.png"
          alt="Interview preview"
          className="w-full h-full object-cover"
        />
      </div>
    </div>
  )
}
