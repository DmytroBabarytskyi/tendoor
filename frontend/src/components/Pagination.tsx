import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number
  pageSize: number
  total: number
  onChange: (p: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (total <= pageSize) return null
  const from = (page - 1) * pageSize + 1
  const to = Math.min(total, page * pageSize)
  return (
    <div className="flex items-center justify-between gap-3 px-1 pt-3 text-sm text-muted-foreground">
      <span className="tabular">
        {from.toLocaleString('uk-UA')}–{to.toLocaleString('uk-UA')} з {total.toLocaleString('uk-UA')}
      </span>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" className="size-8" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Попередня сторінка">
          <ChevronLeft />
        </Button>
        <span className="min-w-16 text-center tabular">
          {page} / {pages}
        </span>
        <Button variant="ghost" size="icon" className="size-8" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Наступна сторінка">
          <ChevronRight />
        </Button>
      </div>
    </div>
  )
}
