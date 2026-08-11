import type {
  FavoriteCategory,
  FavoriteItem,
  FavoriteItemType,
  FavoriteList,
} from '../types/api'
import { apiRequest } from './client'

export function listFavorites(
  itemType?: FavoriteItemType,
  category?: FavoriteCategory,
): Promise<FavoriteList> {
  const params = new URLSearchParams()
  if (itemType) params.set('item_type', itemType)
  if (category) params.set('category', category)
  const query = params.size ? `?${params}` : ''
  return apiRequest<FavoriteList>(`/favorites${query}`)
}

export function createFavorite(
  itemType: FavoriteItemType,
  targetId: number,
  category: FavoriteCategory = 'unclassified',
): Promise<FavoriteItem> {
  return apiRequest<FavoriteItem>('/favorites', {
    method: 'POST',
    body: JSON.stringify({ item_type: itemType, target_id: targetId, category }),
  })
}

export function updateFavoriteNote(
  favoriteId: number,
  note: string | null,
): Promise<FavoriteItem> {
  return apiRequest<FavoriteItem>(`/favorites/${favoriteId}`, {
    method: 'PATCH',
    body: JSON.stringify({ note }),
  })
}

export function updateFavoriteCategory(
  favoriteId: number,
  category: FavoriteCategory,
): Promise<FavoriteItem> {
  return apiRequest<FavoriteItem>(`/favorites/${favoriteId}`, {
    method: 'PATCH',
    body: JSON.stringify({ category }),
  })
}

export function deleteFavorite(favoriteId: number): Promise<void> {
  return apiRequest<void>(`/favorites/${favoriteId}`, { method: 'DELETE' })
}
