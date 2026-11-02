import { useMutation } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { MessagePage, NotFoundPage } from '../components/States'

/** Reached from the footer of any email. A button, not an automatic action, so link
 * scanners that open emails can't unsubscribe anyone by accident. */
export function UnsubscribePage() {
  const { token = '' } = useParams()
  const stop = useMutation({ mutationFn: () => api(`/unsubscribe/${token}`, { method: 'POST' }) })

  if (stop.error instanceof ApiError && stop.error.status === 404) return <NotFoundPage />
  if (stop.isSuccess) {
    return (
      <MessagePage title="Reminders stopped">
        <p style={{ margin: 0 }}>You'll still get your links and draw emails.</p>
      </MessagePage>
    )
  }
  return (
    <MessagePage title="Stop reminder emails?">
      {stop.error && (
        <p className="alert" role="alert" style={{ margin: 0 }}>
          {stop.error.message}
        </p>
      )}
      <button type="button" className="btn btn--main btn--block" disabled={stop.isPending} onClick={() => stop.mutate()}>
        Stop reminders
      </button>
    </MessagePage>
  )
}

export function LeftPage() {
  return (
    <MessagePage title="You've left">
      <p style={{ margin: 0 }}>Your details and wish list have been deleted.</p>
    </MessagePage>
  )
}

export function GroupDeletedPage() {
  return (
    <MessagePage title="Group deleted">
      <p style={{ margin: 0 }}>Everyone's details and wish lists have been deleted.</p>
    </MessagePage>
  )
}
