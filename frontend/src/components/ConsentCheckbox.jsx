import { forwardRef } from 'react'

const ConsentCheckbox = forwardRef(function ConsentCheckbox({ label, checked, onChange }, ref) {
  return (
    <div className="w-full">
      <div ref={ref} className="inline-block transform">
        <label className="flex items-start gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            className="mt-1"
            checked={checked}
            onChange={onChange}
          />
          {label}
        </label>
      </div>
    </div>
  )
})

export default ConsentCheckbox
