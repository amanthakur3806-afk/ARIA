import { Icon } from '../ui/Icon'
import './Brand.css'

export function Brand() {
  return (
    <div aria-label="ARIA" className="brand">
      <span className="brand__mark">
        <Icon name="sparkle" size={21} strokeWidth={1.7} />
      </span>
      <span className="brand__name">ARIA<span></span></span>
    </div>
  )
}
