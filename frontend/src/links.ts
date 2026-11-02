import { useParams } from 'react-router-dom'

/** Paths for whoever holds the link in the URL.
 *
 * The organiser's admin link (/g/...) also opens their own wish list and giftee, so the
 * wish-list and giftee pages work under both /g/:adminToken and /p/:participantToken.
 */
export type MemberLinks = {
  token: string
  organiser: boolean
  home: string
  wishList: string
  giftee: string
}

export function memberLinks(params: { adminToken?: string; participantToken?: string }): MemberLinks {
  if (params.adminToken) {
    const base = `/g/${params.adminToken}`
    return { token: params.adminToken, organiser: true, home: base, wishList: `${base}/wishlist`, giftee: `${base}/giftee` }
  }
  const token = params.participantToken ?? ''
  const base = `/p/${token}`
  return { token, organiser: false, home: base, wishList: base, giftee: `${base}/giftee` }
}

export function useMemberLinks(): MemberLinks {
  return memberLinks(useParams())
}

export type Destination = 'group' | 'wishlist' | 'giftee'

/** Where an opened email link should land. */
export function destinationPath(kind: 'admin' | 'participant', link: string, to: string | null): string {
  const path = new URL(link).pathname
  const token = path.split('/').pop() ?? ''
  const links = memberLinks(kind === 'admin' ? { adminToken: token } : { participantToken: token })
  if (to === 'giftee') return links.giftee
  if (to === 'wishlist') return links.wishList
  return links.home
}
