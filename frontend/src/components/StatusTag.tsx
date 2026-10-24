import type { Status } from '../api'

const LABEL: Record<Status, string> = { new: 'New', quoted: 'Quoted', won: 'Won', lost: 'Lost' }

// Each status has its own glyph so state never relies on color alone.
function Glyph({ status }: { status: Status }) {
  switch (status) {
    case 'new': return <svg viewBox="0 0 10 10" aria-hidden><circle cx="5" cy="5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
    case 'quoted': return <svg viewBox="0 0 10 10" aria-hidden><path d="M5 1.5A3.5 3.5 0 0 1 5 8.5Z" fill="currentColor" /><circle cx="5" cy="5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
    case 'won': return <svg viewBox="0 0 10 10" aria-hidden><path d="M1.5 5.2 4 7.6 8.6 2.4" fill="none" stroke="currentColor" strokeWidth="1.8" /></svg>
    case 'lost': return <svg viewBox="0 0 10 10" aria-hidden><path d="M2 2 8 8M8 2 2 8" stroke="currentColor" strokeWidth="1.8" /></svg>
  }
}

export function StatusTag({ status, buyerView = false }: { status: Status; buyerView?: boolean }) {
  // Buyers read outcomes from their side: they accepted or declined the quote.
  const label = buyerView ? { ...LABEL, new: 'Awaiting quote', quoted: 'Quote received', won: 'Accepted', lost: 'Declined' }[status] : LABEL[status]
  return <span className={`tag tag-${status}`}><Glyph status={status} />{label}</span>
}
