// src/hooks/useMicCheck.js
import { useRef, useState, useCallback } from 'react'
import RecordRTC from 'recordrtc'

export default function useMicCheck(onReady) {
  const [volumeReady, setVolumeReady] = useState(false)
  const [error, setError] = useState(null)
  const recorderRef = useRef(null)
  const streamRef = useRef(null)

  const startCheck = useCallback(() => {
    setError(null)
    setVolumeReady(false)

    navigator.mediaDevices.getUserMedia({ audio: true, video: true })
      .then(async (stream) => {
        streamRef.current = stream

        const audioContext = new (window.AudioContext || window.webkitAudioContext)()
        await audioContext.resume()

        const source = audioContext.createMediaStreamSource(stream)
        const analyser = audioContext.createAnalyser()
        analyser.fftSize = 512
        const dataArray = new Uint8Array(analyser.frequencyBinCount)
        source.connect(analyser)

        let silenceCounter = 0
        const detectVolume = () => {
          analyser.getByteFrequencyData(dataArray)
          const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length
          if (avg > 2) {
            setVolumeReady(true)
            if (onReady) onReady()
            return
          } else {
            silenceCounter++
            if (silenceCounter > 100) {
              setError("Microphone is not active or no input detected")
              return
            }
            requestAnimationFrame(detectVolume)
          }
        }

        detectVolume()

        recorderRef.current = new RecordRTC(stream, {
          type: 'video',
          mimeType: 'video/webm',
          disableLogs: true,
        })

        // Optional: start recording immediately or wait for user action
        // recorderRef.current.startRecording()
      })
      .catch(() => {
        setError("Access to microphone or camera was denied")
      })
  }, [onReady])

  return {
    startCheck,
    volumeReady,
    error,
    recorder: recorderRef,
    stream: streamRef,
  }
}
