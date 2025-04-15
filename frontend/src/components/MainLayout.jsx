import React, { useState } from 'react'
import OpeningScreen from './OpeningScreen'
import GuideScreen from './GuideScreen'

export default function MainLayout() {
  const [stage, setStage] = useState('welcome')
  const [media, setMedia] = useState(null)

  const handleMediaReady = ({ screenStream, audioStream }) => {
    setMedia({ screenStream, audioStream })
    setStage('guide')
  }

  if (stage === 'welcome') {
    return <OpeningScreen 
      onReady={handleMediaReady} 
    />
  }

  if (stage === 'guide') {
    return <GuideScreen
      audioStream={media.audioStream}
      screenStream={media.screenStream}
    />
  }

  return null
}
