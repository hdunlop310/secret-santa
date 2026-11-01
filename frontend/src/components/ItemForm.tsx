import { useRef, useState, type FormEvent } from 'react'
import { api, type WishlistItem } from '../api'
import { formatPence, parsePounds } from '../format'
import { Field } from './Field'

export type ItemInput = {
  title: string
  url: string | null
  price: number | null
  image_url: string | null
}

type Props = {
  token: string
  heading: string
  initial?: WishlistItem
  saving: boolean
  error?: string
  onSave: (item: ItemInput) => Promise<unknown>
  onCancel?: () => void
}

type Preview = { title: string | null; image_url: string | null }

function isValidUrl(url: string): boolean {
  try {
    const u = new URL(url)
    return (u.protocol === 'http:' || u.protocol === 'https:') && Boolean(u.hostname) && !u.username && !u.password
  } catch {
    return false
  }
}

function normaliseUrl(raw: string): string | null {
  const value = raw.trim()
  if (!value) return null
  return /^https?:\/\//i.test(value) ? value : `https://${value}`
}

export function ItemForm({ token, heading, initial, saving, error, onSave, onCancel }: Props) {
  const [title, setTitle] = useState(initial?.title ?? '')
  const [url, setUrl] = useState(initial?.url ?? '')
  const [price, setPrice] = useState(initial?.price != null ? formatPence(initial.price).slice(1) : '')
  const [imageUrl, setImageUrl] = useState<string | null>(initial?.image_url ?? null)
  const [errors, setErrors] = useState<{ title?: string; url?: string; price?: string }>({})
  const previewFor = useRef<string | null>(initial?.url ?? null)
  const titleTouched = useRef(Boolean(initial))

  async function loadPreview() {
    const link = normaliseUrl(url)
    if (!link || !isValidUrl(link) || link === previewFor.current) return
    previewFor.current = link
    setImageUrl(null)
    try {
      const preview = await api<Preview>('/link-preview', { method: 'POST', token, body: { url: link } })
      if (previewFor.current !== link) return
      setImageUrl(preview.image_url)
      if (preview.title && !titleTouched.current) setTitle((t) => t || preview.title!)
    } catch {
      // A preview is a nicety; the item saves without one.
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const link = normaliseUrl(url)
    const pence = price.trim() ? parsePounds(price) : null
    const next = {
      title: title.trim() ? undefined : 'Enter an item',
      url: link && !isValidUrl(link) ? 'Enter a valid link' : undefined,
      price: price.trim() && pence === null ? 'Enter an amount, like 20' : undefined,
    }
    setErrors(next)
    if (next.title || next.url || next.price) return
    try {
      await onSave({
        title: title.trim(),
        url: link,
        price: pence,
        image_url: link && link === previewFor.current ? imageUrl : null,
      })
    } catch {
      return // the error is shown via the `error` prop; keep what was typed
    }
    if (!initial) {
      setTitle('')
      setUrl('')
      setPrice('')
      setImageUrl(null)
      previewFor.current = null
      titleTouched.current = false
    }
  }

  return (
    <form className="add-card" onSubmit={submit} noValidate aria-label={heading}>
      <h2 className="add-card__title">{heading}</h2>
      <Field
        label="Item"
        placeholder="What would you like?"
        value={title}
        maxLength={200}
        onChange={(e) => {
          titleTouched.current = true
          setTitle(e.target.value)
        }}
        error={errors.title}
      />
      <div className="grid-link-price">
        <Field
          label="Link (optional)"
          type="url"
          inputMode="url"
          placeholder="https://"
          value={url}
          maxLength={2048}
          onChange={(e) => setUrl(e.target.value)}
          onBlur={loadPreview}
          error={errors.url}
        />
        <Field
          label="Price (£)"
          inputMode="decimal"
          placeholder="20"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          error={errors.price}
        />
      </div>
      {error && (
        <p className="alert" role="alert" style={{ margin: 0 }}>
          {error}
        </p>
      )}
      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn btn--secondary btn--save" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="submit" className="btn btn--primary btn--save" disabled={saving}>
          {saving ? 'Saving...' : 'Save item'}
        </button>
      </div>
    </form>
  )
}
