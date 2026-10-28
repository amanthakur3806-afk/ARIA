import './Brand.css'

export function Brand() {
  return (
    <div aria-label="ARIA" className="brand">
      <span aria-hidden="true" className="brand__mark">A</span>
      <span className="brand__name">ARIA<span></span></span>
    </div>
  )
}
