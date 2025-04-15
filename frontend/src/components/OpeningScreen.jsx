import React from 'react'
import Blobs from './Blobs'
import NoiseOverlay from './NoiseOverlay'
import MainCard from './MainCard'

export default function OpeningScreen({ onReady }) {
  return (
    <div className="min-h-screen bg-needleebg flex items-center justify-center overflow-hidden">
      <Blobs />
      <NoiseOverlay />
      <MainCard
        title="Screen Guidance"
        subtitle="This tool will guide you step-by-step as you share your screen."
        buttonText="Start"
        consentText="I agree to share my screen and audio during this session."
        onAction={onReady}
      />
    </div>
  )
}
