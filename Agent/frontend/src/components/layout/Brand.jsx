import { Icon } from '../ui/Icon'
import './Brand.css'

export function Brand() {
  return (
    <div aria-label="ARYA" className="brand">
      <span className="brand__mark">
        <Icon name="sparkle" size={21} strokeWidth={1.7} />
      </span>
      <span className="brand__name">arya<span>.</span></span>
    </div>
  )
}
