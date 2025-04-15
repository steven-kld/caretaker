export default function MainButton({ children, onClick }) {
  return (
    <button
      onClick={onClick}
      className="px-6 py-2 rounded-full bg-blue-600 text-white hover:bg-blue-700 transition font-medium"
    >
      {children}
    </button>
  )
}
