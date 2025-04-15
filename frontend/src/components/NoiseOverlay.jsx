export default function NoiseOverlay() {
  return (
    <div
      className="fixed inset-0 z-20 pointer-events-none mix-blend-overlay opacity-5"
      style={{
        backgroundImage: 'url("/textures/noise.png")',
        backgroundSize: '400px 400px',
        backgroundRepeat: 'repeat',
      }}
    />
  )
}
