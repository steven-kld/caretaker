import React, { useState, useEffect } from 'react'
import OpeningScreen from './OpeningScreen'
import GuideScreen from './GuideScreen'
import { initializeSession } from '../api/session'

export default function MainLayout() {
  const [stage, setStage] = useState('welcome')
  const [media, setMedia] = useState(null)

  useEffect(() => {
    initializeSession().catch(err => {
      console.error('❌ Session init failed:', err)
    })
  }, [])

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
