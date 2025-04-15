export default function Blobs() {
    const blobs = [
      { color: 'bg-blobIndigo', size: 'w-[900px] h-[900px]', pos: 'top-[-200px] left-[-200px]', anim: 'animate-blob1' },
      { color: 'bg-blobLavender', size: 'w-[800px] h-[800px]', pos: 'bottom-[-150px] left-[30vw]', anim: 'animate-blob2' },
      { color: 'bg-blobSteel', size: 'w-[900px] h-[900px]', pos: 'top-[30vh] right-[-250px]', anim: 'animate-blob3' },
      { color: 'bg-blobIce', size: 'w-[1100px] h-[1100px]', pos: 'bottom-[-200px] right-[25vw]', anim: 'animate-blob4' },
      { color: 'bg-blobCloud', size: 'w-[850px] h-[850px]', pos: 'top-[10vh] left-[60vw]', anim: 'animate-blob5' },
    ]
  
    return (
      <div className="pointer-events-none fixed inset-0 z-10 overflow-hidden">
        {blobs.map((b, i) => (
          <div
            key={i}
            className={`absolute rounded-full ${b.size} ${b.pos} ${b.anim} ${b.color} blur-[120px] will-change-transform`}
          />
        ))}
      </div>
    )
  }
  