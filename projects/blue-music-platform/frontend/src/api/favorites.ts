import type { FavoriteItem, FavoriteItemType, FavoriteList } from '../types/api'
import { apiRequest } from './client'

export function listFavorites(itemType?: FavoriteItemType): Promise<FavoriteList> {
  const query = itemType ? `?item_type=${itemType}` : ''
  return apiRequest<FavoriteList>(`/favorites${query}`)
}

export function createFavorite(
  itemType: FavoriteItemType,
  targetId: number,
): Promise<FavoriteItem> {
  return apiRequest<FavoriteItem>('/favorites', {
    method: 'POST',
    body: JSON.stringify({ item_type: itemType, target_id: targetId }),
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

export function deleteFavorite(favoriteId: number): Promise<void> {
  return apiRequest<void>(`/favorites/${favoriteId}`, { method: 'DELETE' })
}
