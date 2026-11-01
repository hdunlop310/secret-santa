import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, type GroupCreate, type GroupCreated } from '../api'
import { CopyLink } from '../components/CopyLink'
import { Field, TextAreaField } from '../components/Field'
import { HeaderBand } from '../components/HeaderBand'
import { parsePounds, todayIso } from '../format'

type Form = {
  name: string
  gift_date: string
  budget_min: string
  budget_max: string
  message: string
  admin_name: string
  admin_email: string
  admin_participates: boolean
}

type Errors = Partial<Record<keyof Form, string>>

const EMPTY: Form = {
  name: '',
  gift_date: '',
  budget_min: '',
  budget_max: '',
  message: '',
  admin_name: '',
  admin_email: '',
  admin_participates: true,
}

export function validate(form: Form): { errors: Errors; payload?: GroupCreate } {
  const errors: Errors = {}
  if (!form.name.trim()) errors.name = 'Enter a group name'
  if (!form.gift_date) errors.gift_date = 'Choose a date'
  else if (form.gift_date < todayIso()) errors.gift_date = "The date can't be in the past"
  const min = parsePounds(form.budget_min)
  const max = parsePounds(form.budget_max)
  if (min === null) errors.budget_min = 'Enter an amount, like 15'
  if (max === null) errors.budget_max = 'Enter an amount, like 25'
  else if (min !== null && max < min) errors.budget_max = 'Must be at least the min'
  if (!form.admin_name.trim()) errors.admin_name = 'Enter your name'
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.admin_email.trim())) errors.admin_email = 'Enter a valid email'
  if (Object.keys(errors).length > 0) return { errors }
  return {
    errors,
    payload: {
      name: form.name.trim(),
      gift_date: form.gift_date,
      budget_min: min!,
      budget_max: max!,
      message: form.message.trim() || null,
      admin_name: form.admin_name.trim(),
      admin_email: form.admin_email.trim(),
      admin_participates: form.admin_participates,
    },
  }
}

export function CreateGroupPage() {
  const [form, setForm] = useState<Form>(EMPTY)
  const [errors, setErrors] = useState<Errors>({})
  const create = useMutation({
    mutationFn: (payload: GroupCreate) => api<GroupCreated>('/groups', { method: 'POST', body: payload }),
  })

  if (create.data) return <GroupCreatedView created={create.data} />

  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  function submit(e: FormEvent) {
    e.preventDefault()
    const { errors, payload } = validate(form)
    setErrors(errors)
    if (payload) create.mutate(payload)
  }

  return (
    <main className="page">
      <HeaderBand aside="Step 1 of 2">
        <h1 className="band__title">Create a Secret Santa</h1>
      </HeaderBand>
      <form className="content content--form" onSubmit={submit} noValidate>
        <Field label="Group name" placeholder="e.g. Family Secret Santa" value={form.name} onChange={set('name')} error={errors.name} maxLength={80} />
        <Field label="Gift exchange date" type="date" min={todayIso()} value={form.gift_date} onChange={set('gift_date')} error={errors.gift_date} />
        <div className="grid-2">
          <Field label="Min budget (£)" inputMode="decimal" placeholder="15" value={form.budget_min} onChange={set('budget_min')} error={errors.budget_min} />
          <Field label="Max budget (£)" inputMode="decimal" placeholder="25" value={form.budget_max} onChange={set('budget_max')} error={errors.budget_max} />
        </div>
        <TextAreaField label="Message to the group (optional)" placeholder="Rules, theme, where to meet..." value={form.message} onChange={set('message')} maxLength={500} />
        <h2 className="divider-heading" style={{ margin: '2px 0 0' }}>
          About you
        </h2>
        <div className="grid-2">
          <Field label="Your name" placeholder="Sam" autoComplete="name" value={form.admin_name} onChange={set('admin_name')} error={errors.admin_name} maxLength={60} />
          <Field label="Your email" type="email" placeholder="you@email.com" autoComplete="email" value={form.admin_email} onChange={set('admin_email')} error={errors.admin_email} />
        </div>
        <div className="checkbox">
          <input
            id="admin-participates"
            type="checkbox"
            checked={form.admin_participates}
            onChange={(e) => setForm((f) => ({ ...f, admin_participates: e.target.checked }))}
          />
          <label htmlFor="admin-participates">I'm taking part too</label>
        </div>
        {create.error && (
          <p className="alert" role="alert" style={{ margin: 0 }}>
            {create.error.message}
          </p>
        )}
        <button type="submit" className="btn btn--primary btn--block" disabled={create.isPending}>
          {create.isPending ? 'Creating...' : 'Create group'}
        </button>
      </form>
    </main>
  )
}

function GroupCreatedView({ created }: { created: GroupCreated }) {
  const adminPath = new URL(created.admin_link).pathname
  return (
    <main className="page">
      <HeaderBand aside="Step 2 of 2">
        <h1 className="band__title">Your group is ready</h1>
        <p className="band__facts">We've emailed you these links too.</p>
      </HeaderBand>
      <div className="content">
        <CopyLink label="Your admin link" url={created.admin_link} />
        {created.participant_link && <CopyLink label="Your personal link" url={created.participant_link} />}
        <Link className="btn btn--primary btn--block" to={adminPath}>
          Go to your group
        </Link>
      </div>
    </main>
  )
}
