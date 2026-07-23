"use client";

import Link from "next/link";
import { ArrowLeft, BellRing, MessageCircleWarning, Moon, SlidersHorizontal } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import {
  notificationFrequencyLabel,
  notificationSeverityLabel
} from "@/lib/formatters";
import { useMockState } from "@/lib/mock-state";

const inAppToggles = [
  { key: "global", label: "站内通知总开关", enabled: true },
  { key: "daily-review", label: "每日复盘通知", enabled: true },
  { key: "announcement", label: "重大公告通知", enabled: true },
  { key: "anomaly", label: "自选股异动通知", enabled: true },
  { key: "observation", label: "观察条件验证通知", enabled: true },
  { key: "valuation", label: "估值更新通知", enabled: true }
];

export default function NotificationSettingsPage() {
  const { data } = useMockState();
  const wechatIdentity = data.externalIdentities[0];

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="设置"
        title="通知设置"
        description="配置站内通知偏好，预留微信公众号、邮件、Web Push和移动Push扩展能力。"
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
              本页面仅用于产品原型验证。不会发起扫码、OAuth、模板消息、API调用或真实绑定。
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <BellRing className="h-5 w-5 text-blue-700" />
          <h2 className="text-lg font-semibold text-slate-950">站内通知偏好</h2>
          <SimulatedDataBadge compact />
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {inAppToggles.map((item) => (
            <label key={item.key} className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 p-3">
              <span className="text-sm font-medium text-slate-800">{item.label}</span>
              <input
                type="checkbox"
                checked={item.enabled}
                readOnly
                className="h-4 w-4 rounded border-slate-300 text-slate-900"
              />
            </label>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-500">
          普通用户可以关闭非必要通知；系统严重故障和账户安全类通知不应被AI提升或篡改。
        </p>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <MessageCircleWarning className="h-5 w-5 text-emerald-700" />
            <h2 className="text-lg font-semibold text-slate-950">微信公众号Mock状态</h2>
          </div>
          <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-sm font-semibold text-slate-950">
              {wechatIdentity ? wechatStatusLabel(wechatIdentity.bindStatus) : "未绑定"}
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              OpenID仅作为外部身份，不是用户主键；UnionID可选。失败不会影响站内通知、复盘、估值或行情展示。
            </p>
            <p className="mt-2 text-xs text-slate-500">
              账号：{wechatIdentity?.providerAccountId ?? "暂无"}；外部ID：{wechatIdentity?.providerUserId ?? "暂无"}
            </p>
          </div>
          <div className="mt-3 rounded-md border border-slate-200 bg-white p-3">
            <p className="text-xs font-semibold text-slate-500">微信摘要预览（Mock）</p>
            <p className="mt-2 text-sm leading-6 text-slate-700">
              今日复盘已生成：重大公告 1 条，重要异动 1 条，待验证观察条件 5 条。点击进入站内完整页面查看。
            </p>
            <p className="mt-2 text-xs text-slate-500">
              摘要不得包含完整自选股清单、API Key、敏感账户信息、交易动作或保证性表述。
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-5 w-5 text-slate-700" />
            <h2 className="text-lg font-semibold text-slate-950">事件偏好矩阵</h2>
          </div>
          <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
            <div className="grid grid-cols-[1.1fr_0.8fr_0.8fr_0.7fr] bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
              <span>事件</span>
              <span>通道</span>
              <span>频率</span>
              <span>最低级别</span>
            </div>
            {data.notificationPreferences.map((pref) => (
              <div key={pref.id} className="grid grid-cols-[1.1fr_0.8fr_0.8fr_0.7fr] gap-2 border-t border-slate-100 px-3 py-2 text-xs text-slate-700">
                <span className="truncate">{pref.eventType}</span>
                <span>{pref.channel}</span>
                <span>{pref.enabled ? notificationFrequencyLabel(pref.frequency) : "关闭"}</span>
                <span>{notificationSeverityLabel(pref.minSeverity)}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center gap-2">
              <Moon className="h-4 w-4 text-slate-700" />
              <p className="text-sm font-semibold text-slate-950">免打扰时间</p>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              {data.notificationPreferences.find((item) => item.quietHours)?.quietHours ?? "22:30-08:00"}，非紧急通知延后发送，重大公告和高严重级别观察条件可立即提醒。
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

function wechatStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    unbound: "未绑定",
    "bound-subscribed": "已绑定且已关注",
    "bound-unsubscribed": "已绑定但未关注",
    "authorization-invalid": "绑定授权失效",
    "channel-unavailable": "通道不可用"
  };

  return labels[status] ?? status;
}
