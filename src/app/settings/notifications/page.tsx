"use client";

import Link from "next/link";
import { ArrowLeft, BellRing, MessageCircleWarning, Moon, Save, SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import {
  listNotificationPreferences,
  updateNotificationPreferences
} from "@/lib/api/notifications";
import type {
  InAppNotificationSeverity,
  NotificationEventType,
  NotificationFrequency,
  NotificationPreference,
  NotificationPreferenceUpdateItem
} from "@/lib/api/types";

const frequencyOptions: Array<{ value: NotificationFrequency; label: string }> = [
  { value: "immediate", label: "立即" },
  { value: "daily_digest", label: "每日摘要" },
  { value: "disabled", label: "关闭" }
];

const severityOptions: Array<{ value: InAppNotificationSeverity; label: string }> = [
  { value: "info", label: "普通" },
  { value: "notice", label: "提醒" },
  { value: "important", label: "重要" }
];

export default function NotificationSettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [preferences, setPreferences] = useState<NotificationPreference[]>([]);
  const [drafts, setDrafts] = useState<Partial<Record<NotificationEventType, NotificationPreferenceUpdateItem>>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const orderedDrafts = useMemo(
    () =>
      preferences
        .map((preference) => drafts[preference.event_type])
        .filter((item): item is NotificationPreferenceUpdateItem => Boolean(item)),
    [drafts, preferences]
  );

  const refreshPreferences = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await listNotificationPreferences();
      setPreferences(items);
      setDrafts(Object.fromEntries(items.map((item) => [item.event_type, toDraft(item)])) as Record<NotificationEventType, NotificationPreferenceUpdateItem>);
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !user) {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      void refreshPreferences();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [authLoading, refreshPreferences, user]);

  function updateDraft(eventType: NotificationEventType, patch: Partial<NotificationPreferenceUpdateItem>) {
    setDrafts((current) => {
      const existing = current[eventType];
      if (!existing) {
        return current;
      }
      const next = { ...existing, ...patch };
      if (patch.frequency === "disabled") {
        next.enabled = false;
      } else if (patch.frequency) {
        next.enabled = true;
      }
      return { ...current, [eventType]: next };
    });
    setSuccess(null);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await updateNotificationPreferences(orderedDrafts);
      setPreferences(updated);
      setDrafts(Object.fromEntries(updated.map((item) => [item.event_type, toDraft(item)])) as Record<NotificationEventType, NotificationPreferenceUpdateItem>);
      setSuccess("站内通知偏好已保存。");
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSaving(false);
    }
  }

  if (authLoading) {
    return <LoadingSkeleton lines={6} />;
  }

  if (!user) {
    return <ErrorState title="需要登录" description="通知偏好只允许当前登录用户查看和修改。" />;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="设置"
        title="通知设置"
        description="站内通知偏好接真实 API；微信、邮件、Web Push 和移动 Push 仍未接入。"
        actions={
          <Link
            href="/settings"
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            返回设置
          </Link>
        }
      />

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <MessageCircleWarning className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
          <div>
            <h2 className="font-semibold text-amber-950">微信公众号能力尚未接入</h2>
            <p className="mt-1 text-sm leading-6 text-amber-900">
              微信公众号能力尚未接入，本区域仅展示未来产品规划。当前不会创建二维码、OAuth、OpenID、模板消息或微信 API 调用。
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <BellRing className="h-5 w-5 text-blue-700" />
              <h2 className="text-lg font-semibold text-slate-950">站内通知偏好</h2>
              <span className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-800">
                真实API
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-600">
              daily_digest 当前表示不产生单独即时通知，而是进入每日复盘材料；免打扰时间仅为未来外部推送预留。
            </p>
          </div>
          <button
            onClick={handleSave}
            disabled={saving || orderedDrafts.length === 0}
            className="focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="button"
          >
            <Save className="h-4 w-4" />
            {saving ? "保存中" : "保存偏好"}
          </button>
        </div>

        {success ? (
          <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            {success}
          </div>
        ) : null}
        {error ? <div className="mt-3"><ErrorState title="通知偏好错误" description={error} /></div> : null}

        <div className="mt-4">
          {loading ? <LoadingSkeleton lines={6} /> : null}
          {!loading && preferences.length > 0 ? (
            <div className="grid gap-2">
              {preferences.map((preference) => {
                const draft = drafts[preference.event_type];
                if (!draft) {
                  return null;
                }
                return (
                  <PreferenceRow
                    key={preference.id}
                    eventType={preference.event_type}
                    draft={draft}
                    onChange={(patch) => updateDraft(preference.event_type, patch)}
                  />
                );
              })}
            </div>
          ) : null}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <MessageCircleWarning className="h-5 w-5 text-emerald-700" />
            <h2 className="text-lg font-semibold text-slate-950">微信公众号规划区</h2>
          </div>
          <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-sm font-semibold text-slate-950">未绑定，且当前不可绑定</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              未来微信渠道只会作为通知通道扩展，不会成为用户主键；当前阶段不保存 OpenID、UnionID 或任何真实微信配置。
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-5 w-5 text-slate-700" />
            <h2 className="text-lg font-semibold text-slate-950">实现边界</h2>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <BoundaryCard
              icon={<Moon className="h-4 w-4 text-slate-700" />}
              title="免打扰时间"
              description="当前仅保存设置值；站内通知仍会即时显示，不因免打扰延迟。"
            />
            <BoundaryCard
              icon={<BellRing className="h-4 w-4 text-slate-700" />}
              title="严重级别"
              description="severity 由程序规则确定；AI 风险级别不得直接提升通知严重程度。"
            />
          </div>
        </div>
      </section>
    </div>
  );
}

function PreferenceRow({
  eventType,
  draft,
  onChange
}: {
  eventType: NotificationEventType;
  draft: NotificationPreferenceUpdateItem;
  onChange: (patch: Partial<NotificationPreferenceUpdateItem>) => void;
}) {
  return (
    <div className="grid gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 lg:grid-cols-[1.1fr_120px_160px_150px_1fr] lg:items-center">
      <div>
        <p className="text-sm font-semibold text-slate-950">{eventTypeLabel(eventType)}</p>
        <p className="mt-1 text-xs text-slate-500">{eventType}</p>
      </div>
      <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
        <input
          type="checkbox"
          checked={draft.enabled}
          onChange={(event) =>
            onChange({
              enabled: event.target.checked,
              frequency: event.target.checked && draft.frequency === "disabled" ? "immediate" : draft.frequency
            })
          }
          className="h-4 w-4 rounded border-slate-300"
        />
        开启
      </label>
      <label className="grid gap-1 text-xs font-medium text-slate-600">
        频率
        <select
          value={draft.frequency}
          onChange={(event) => onChange({ frequency: event.target.value as NotificationFrequency })}
          className="focus-ring h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700"
        >
          {frequencyOptions.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-1 text-xs font-medium text-slate-600">
        最低级别
        <select
          value={draft.minimum_severity}
          onChange={(event) => onChange({ minimum_severity: event.target.value as InAppNotificationSeverity })}
          className="focus-ring h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700"
        >
          {severityOptions.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-xs font-medium text-slate-600">
          免打扰开始
          <input
            type="time"
            value={timeInputValue(draft.quiet_hours_start)}
            onChange={(event) => onChange({ quiet_hours_start: event.target.value || null })}
            className="focus-ring h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700"
          />
        </label>
        <label className="grid gap-1 text-xs font-medium text-slate-600">
          免打扰结束
          <input
            type="time"
            value={timeInputValue(draft.quiet_hours_end)}
            onChange={(event) => onChange({ quiet_hours_end: event.target.value || null })}
            className="focus-ring h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700"
          />
        </label>
      </div>
    </div>
  );
}

function BoundaryCard({
  icon,
  title,
  description
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-sm font-semibold text-slate-950">{title}</p>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
    </div>
  );
}

function toDraft(preference: NotificationPreference): NotificationPreferenceUpdateItem {
  return {
    event_type: preference.event_type,
    enabled: preference.enabled,
    frequency: preference.frequency,
    minimum_severity: preference.minimum_severity,
    quiet_hours_start: timeInputValue(preference.quiet_hours_start),
    quiet_hours_end: timeInputValue(preference.quiet_hours_end),
    timezone: preference.timezone || "Asia/Shanghai"
  };
}

function timeInputValue(value?: string | null): string {
  if (!value) {
    return "";
  }
  return value.slice(0, 5);
}

function eventTypeLabel(eventType: NotificationEventType): string {
  const labels: Record<NotificationEventType, string> = {
    "user_daily_review.generated": "每日复盘已生成",
    "user_daily_review.partial": "复盘部分完成",
    "user_daily_review.failed": "复盘失败",
    "user_daily_review.became_stale": "复盘需要更新",
    "information.high_priority_detected": "重要信息",
    "information.verification_required": "待核实事项",
    "ai_task.failed": "AI分析失败",
    "research_task.created": "研究事项已创建",
    "research_task.status_changed": "研究事项状态更新",
    "research_task.due": "研究事项到期",
    "observation_condition.due": "观察条件到期"
  };
  return labels[eventType];
}
