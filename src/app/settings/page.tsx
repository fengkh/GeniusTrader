"use client";

import Link from "next/link";
import { ShieldCheck } from "lucide-react";

import { PlaceholderPage } from "@/components/layout/PlaceholderPage";
import { MockRoleSwitcher } from "@/components/mock/MockRoleSwitcher";
import { MockScenarioSwitcher } from "@/components/mock/MockScenarioSwitcher";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { useMockState } from "@/lib/mock-state";

export default function SettingsPage() {
  const { role } = useMockState();

  return (
    <PlaceholderPage
      eyebrow="设置与更多"
      title="设置"
      description="本轮只保留设置页占位和移动端更多入口，不实现真实表单、权限或密钥保存。"
      items={[
        "普通个人设置：时区、日期格式、数字展示偏好、默认首页视图、是否显示已退市股票、基础界面偏好",
        "AI接口配置：Base URL、API Key、模型名称、默认模型和备用模型",
        "模型任务配置：不同AI任务的模型偏好",
        "通知设置：站内通知偏好与微信公众号Mock状态",
        "数据源状态：最后更新时间、当前同步状态、来源和失败提示",
        ...(role === "admin" ? ["管理员账户管理：管理员Mock身份可见入口"] : [])
      ]}
      extra={
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <ShieldCheck className="h-4 w-4 text-blue-700" />
              移动端更多
            </div>
            <p className="text-sm leading-6 text-slate-600">
              当前页在移动端底部导航中显示为“更多”，集中展示设置入口、当前身份、Mock场景切换和模拟数据说明。
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <MockRoleSwitcher />
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <MockScenarioSwitcher />
            <div className="mt-3">
              <SimulatedDataBadge />
            </div>
          </div>
          <Link
            href="/settings/notifications"
            className="focus-ring rounded-lg border border-slate-200 bg-white p-4 hover:bg-slate-50"
          >
            <p className="text-sm font-semibold text-slate-950">通知设置</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              查看站内通知偏好、微信公众号Mock状态和免打扰时间。
            </p>
          </Link>
        </div>
      }
    />
  );
}
