import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  ApiMessage,
  InAppNotification,
  InAppNotificationStatus,
  NotificationAction,
  NotificationEventType,
  NotificationPreference,
  NotificationPreferenceUpdateItem,
  NotificationUnreadCount,
  Page,
  UUID
} from "@/lib/api/types";

export interface NotificationListParams {
  status?: InAppNotificationStatus | "";
  event_type?: NotificationEventType | "";
  limit?: number;
  offset?: number;
}

export async function listNotifications(
  params: NotificationListParams = {}
): Promise<Page<InAppNotification>> {
  return apiRequest<Page<InAppNotification>>(
    `/notifications${toQueryString({
      status: params.status,
      event_type: params.event_type,
      limit: params.limit ?? 30,
      offset: params.offset ?? 0
    })}`
  );
}

export async function getNotification(notificationId: UUID): Promise<InAppNotification> {
  return apiRequest<InAppNotification>(`/notifications/${notificationId}`);
}

export async function patchNotification(
  notificationId: UUID,
  action: NotificationAction
): Promise<InAppNotification> {
  return apiRequest<InAppNotification>(`/notifications/${notificationId}`, {
    method: "PATCH",
    body: JSON.stringify({ action })
  });
}

export async function markAllNotificationsRead(payload: {
  event_type?: NotificationEventType | null;
  date_from?: string | null;
  date_to?: string | null;
} = {}): Promise<ApiMessage> {
  return apiRequest<ApiMessage>("/notifications/mark-all-read", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getUnreadNotificationCount(): Promise<NotificationUnreadCount> {
  return apiRequest<NotificationUnreadCount>("/notifications/unread-count", {
    redirectOnUnauthorized: false
  });
}

export async function listNotificationPreferences(): Promise<NotificationPreference[]> {
  return apiRequest<NotificationPreference[]>("/notification-preferences");
}

export async function updateNotificationPreferences(
  items: NotificationPreferenceUpdateItem[]
): Promise<NotificationPreference[]> {
  return apiRequest<NotificationPreference[]>("/notification-preferences", {
    method: "PUT",
    body: JSON.stringify({ items })
  });
}
