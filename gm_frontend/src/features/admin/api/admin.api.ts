import client from '../../../lib/api-client'
import { ENDPOINTS } from '../../../lib/endpoints'
import type { LibrarySong } from '../../songs/api/songs.api'

export interface CreditPlan {
  id: number
  slug: string
  name: string
  credits_per_month: number
  price_usd: string
  stripe_price_id: string
  features: string[]
  is_active: boolean
}

export interface StripePrice {
  price_id: string
  amount: number
  currency: string
  interval: string
  active: boolean
}

export interface CreateStripePriceRequest {
  name: string
  price_usd: number
  interval: 'month' | 'year'
}

export interface MonthlySeriesPoint {
  month: number
  label: string
  revenue_usd: number
  new_users: number
  songs_generated: number
}

export interface PlanDistributionItem {
  slug: string
  name: string
  users_count: number
  percentage: number
}

export interface RecentDashboardUser {
  id: string
  full_name: string
  email: string
  plan_name: string
  is_active: boolean
  is_staff: boolean
  created_at: string
}

export interface DashboardMetrics {
  total_users: number
  new_users_30d: number
  active_subscriptions: number
  total_songs_generated: number
  songs_last_30d: number
  failed_jobs_30d: number
  monthly_revenue_usd: number
  annual_revenue_usd: number
  churn_rate_pct: number
  monthly_series: MonthlySeriesPoint[]
  plans_distribution: PlanDistributionItem[]
  recent_users: RecentDashboardUser[]
}

export interface AdminUser {
  id: string
  full_name: string
  email: string
  credit_balance: number
  is_active: boolean
  is_staff: boolean
  role: string
  plan_name: string
  created_at: string
}

export interface AdminUserUpdatePayload {
  is_staff?: boolean
  is_active?: boolean
  role?: 'admin' | 'user'
}

export interface UsageStats {
  total_users: number
  new_users_30d: number
  total_songs_generated: number
  songs_last_30d: number
  failed_jobs_30d: number
  public_songs: number
}

export interface TopSong extends LibrarySong {
  play_count?: number
}

export const adminApi = {
  getDashboardMetrics: () =>
    client.get<DashboardMetrics>(ENDPOINTS.reports.dashboard).then((r) => r.data),

  getUsageStats: () => client.get<UsageStats>(ENDPOINTS.reports.usage).then((r) => r.data),

  getTopSongs: async (): Promise<TopSong[]> => {
    const { data } = await client.get<TopSong[]>(ENDPOINTS.reports.topSongs)
    const needsPlayCount = data.filter((song) => typeof song.play_count !== 'number')
    if (needsPlayCount.length === 0) {
      return data
    }
    const details = await Promise.allSettled(
      needsPlayCount.map((s) =>
        client.get<{ id: string; play_count?: number }>(ENDPOINTS.songs.detail(s.id)).then((r) => r.data)
      )
    )
    const countMap = new Map<string, number>()
    details.forEach((res) => {
      if (res.status === 'fulfilled' && typeof res.value.play_count === 'number') {
        countMap.set(res.value.id, res.value.play_count)
      }
    })
    return data.map((song) => ({
      ...song,
      play_count: song.play_count ?? countMap.get(song.id) ?? 0,
    }))
  },

  getAdminUsers: (search?: string) =>
    client
      .get<AdminUser[]>(ENDPOINTS.reports.users, {
        params: search?.trim() ? { search: search.trim() } : undefined,
      })
      .then((r) => r.data),

  updateAdminUser: (id: string, payload: AdminUserUpdatePayload) =>
    client.patch<AdminUser>(ENDPOINTS.reports.userDetail(id), payload).then((r) => r.data),

  getPlans: (all = false) =>
    client
      .get<CreditPlan[]>(`${ENDPOINTS.credits.plans}${all ? '?all=1' : ''}`)
      .then((r) => r.data),

  createPlan: (data: Omit<CreditPlan, 'id'>) =>
    client.post<CreditPlan>(ENDPOINTS.credits.plans, data).then((r) => r.data),

  updatePlan: (id: number, data: Partial<Omit<CreditPlan, 'id'>>) =>
    client.put<CreditPlan>(ENDPOINTS.credits.planDetail(id), data).then((r) => r.data),

  deletePlan: (id: number) => client.delete(ENDPOINTS.credits.planDetail(id)),

  getStripePrices: () =>
    client.get<StripePrice[]>(ENDPOINTS.credits.stripePrices).then((r) => r.data),

  createStripePrice: (data: CreateStripePriceRequest) =>
    client
      .post<{ stripe_price_id: string }>(ENDPOINTS.credits.stripePrices, data)
      .then((r) => r.data),

  deleteStripePrice: (priceId: string) =>
    client.delete(ENDPOINTS.credits.stripePriceDetail(priceId)).then((r) => r.data),
}
