import { useId, type InputHTMLAttributes, type TextareaHTMLAttributes } from 'react'

type Common = { label: string; error?: string }

function useFieldIds(id: string | undefined, error: string | undefined) {
  const autoId = useId()
  const inputId = id ?? autoId
  const errorId = `${inputId}-error`
  return {
    inputId,
    errorId,
    aria: {
      'aria-invalid': error ? true : undefined,
      'aria-describedby': error ? errorId : undefined,
    },
  }
}

function FieldShell({ label, error, inputId, errorId, children }: Common & {
  inputId: string
  errorId: string
  children: React.ReactNode
}) {
  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      {children}
      {error && (
        <span id={errorId} className="field__error">
          {error}
        </span>
      )}
    </div>
  )
}

export function Field({ label, error, id, ...input }: Common & InputHTMLAttributes<HTMLInputElement>) {
  const { inputId, errorId, aria } = useFieldIds(id, error)
  return (
    <FieldShell label={label} error={error} inputId={inputId} errorId={errorId}>
      <input id={inputId} className="input" {...aria} {...input} />
    </FieldShell>
  )
}

export function TextAreaField({
  label,
  error,
  id,
  ...textarea
}: Common & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { inputId, errorId, aria } = useFieldIds(id, error)
  return (
    <FieldShell label={label} error={error} inputId={inputId} errorId={errorId}>
      <textarea id={inputId} className="input" {...aria} {...textarea} />
    </FieldShell>
  )
}
