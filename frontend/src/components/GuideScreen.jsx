import React, { useEffect, useRef, useState } from 'react'
import RecordRTC from 'recordrtc'
import Blobs from './Blobs'
import NoiseOverlay from './NoiseOverlay'
import { API_URL } from '@/config/api'

export default function GuideScreen({ audioStream, screenStream }) {
  const [agentState, setAgentState] = useState('waiting')

  const audioCtxRef = useRef(null)
  const analyserRef = useRef(null)
  const dataArrayRef = useRef(null)
  const recorderRef = useRef(null)
  const videoRef = useRef()
  const audioPlayerRef = useRef(new Audio())

  const canvasRef = useRef(document.createElement('canvas'))
  const latestFrames = useRef([])
  const frameInterval = useRef(null)
  const startTime = useRef(null)

  useEffect(() => {
    if (videoRef.current && screenStream) {
      videoRef.current.srcObject = screenStream
    }
  }, [screenStream])

  useEffect(() => {
    console.log('🟢 useEffect init: silence detection starting')
    const audioCtx = new AudioContext()
    const source = audioCtx.createMediaStreamSource(audioStream)
    const analyser = audioCtx.createAnalyser()
    analyser.fftSize = 1024
  
    const dataArray = new Float32Array(analyser.fftSize)
    source.connect(analyser)
  
    audioCtxRef.current = audioCtx
    analyserRef.current = analyser
    dataArrayRef.current = dataArray
  
    let silenceStart = null
    let isRecording = false
    let recorder = null
    let timeout = null
  
    const loop = () => {
      analyser.getFloatTimeDomainData(dataArray)
      const max = Math.max(...dataArray.map(Math.abs))
      const now = Date.now()
  
      if (!isRecording && max > 0.15) {
        recorder = new RecordRTC(audioStream, {
          type: 'audio',
          mimeType: 'audio/webm',
          disableLogs: true
        })
        recorder.startRecording()
        recorderRef.current = recorder
        isRecording = true
        setAgentState('listening')
        document.title = 'listening'
        
        latestFrames.current = []
        startTime.current = Date.now()
  
        frameInterval.current = setInterval(() => {
          captureFrame()
        }, 2500)
  
        timeout = setTimeout(() => {
          console.log('⏲️ Timeout reached (15s) – stopping recording')
          stopRecordingAndProcess()
        }, 15000)
      }
  
      if (isRecording) {
        if (max < 0.15) {
          if (!silenceStart) {
            silenceStart = now
            console.log('🔇 Silence started')
          }
          if (now - silenceStart > 1000) {
            console.log('🛑 Silence > 1s – stopping recording')
            clearTimeout(timeout)
            stopRecordingAndProcess()
            return
          }
        } else {
          if (silenceStart) {
            console.log('🔊 Voice resumed – resetting silence timer')
          }
          silenceStart = null
        }
      }
  
      if (agentState === 'waiting' || agentState === 'listening') {
        requestAnimationFrame(loop)
      } else {
        console.log('⛔ Loop paused – current agentState:', agentState)
      }
    }
  
    const stopRecordingAndProcess = () => {
      if (!recorderRef.current) return
      clearInterval(frameInterval.current)
  
      console.log('🛑 Stopping recorder and sending data')
      recorderRef.current.stopRecording(() => {
        const audioBlob = recorderRef.current.getBlob()
        const durationSeconds = Math.round((Date.now() - startTime.current) / 1000)
  
        const framesToSend = latestFrames.current.slice(0, durationSeconds)
        isRecording = false
        recorderRef.current = null
        setAgentState('thinking')
        document.title = 'thinking'

        sendToBackend(audioBlob, framesToSend)
      })
    }
  
    const captureFrame = () => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas) return
  
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
  
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
  
      canvas.toBlob(blob => {
        if (blob) {
          latestFrames.current.push(blob)
          console.log(`📸 Captured frame #${latestFrames.current.length}`)
        }
      }, 'image/jpeg', 0.7)
    }
  
    const sendToBackend = async (audioBlob, frameBlobs) => {
      console.log('📤 Sending to backend:', {
        audioBlob,
        frameCount: frameBlobs.length
      })
  
      const form = new FormData()
      form.append('audio', audioBlob, 'voice.webm')
  
      frameBlobs.forEach((blob, i) => {
        form.append('images', blob, `frame_${i}.jpg`)
      })
  
      fetch('/api/process', {
        method: 'POST',
        body: form
      })
        .then(res => res.blob())
        .then(blob => {
          const url = URL.createObjectURL(blob)
          const player = audioPlayerRef.current
          player.src = url
          setAgentState('playing')
          document.title = 'playing'
          console.log('🔊 Playing audio response')
          player.play()
  
          player.onended = () => {
            console.log('🔁 Audio ended – resetting to waiting')
            setAgentState('waiting')
            document.title = 'waiting'
            requestAnimationFrame(loop)
          }
        })
        .catch(err => {
          console.error('❌ Failed to play audio:', err)
          setAgentState('waiting')
          document.title = 'waiting'
          requestAnimationFrame(loop)
        })
    }
  
    loop()
  
    return () => {
      console.log('🧹 Cleaning up audio context + intervals')
      recorderRef.current?.stopRecording()
      clearTimeout(timeout)
      clearInterval(frameInterval.current)
      audioCtx.close()
    }
  }, [audioStream])

  const stateText = {
    waiting: '🕓 Waiting for your voice...',
    listening: '🎙️ Listening...',
    thinking: '🤖 Thinking...',
    playing: '▶️ Playing response...'
  }

  return (
    <div className="min-h-screen bg-needleebg flex items-center justify-center overflow-hidden relative">
      <Blobs />
      <NoiseOverlay />

      <div className="z-10 w-full max-w-5xl rounded-3xl bg-white shadow-xl p-10 flex items-center justify-between animate-fadeInUp">
        <div className="w-64 h-36 border border-gray-300 shadow rounded-xl overflow-hidden">
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            onLoadedMetadata={() => videoRef.current?.play()}
            className="w-full h-full object-cover"
          />
        </div>
        <div className="text-lg font-medium text-gray-800 px-6 py-4">
          {stateText[agentState]}
        </div>
      </div>
    </div>
  )
}
