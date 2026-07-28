"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, ShieldCheck } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <PlaceholderPage
      eyebrow="设置与更多"
      title="设置"
      description="私人测试版设置入口。AI、通知、数据源和管理员页面均按真实登录身份展示。"
      items={[
        "普通个人设置：时区、日期格式、数字展示偏好、默认首页视图、是否显示已退市股票、基础界面偏好",
        "AI接口配置：Base URL、API Key、模型名称、默认模型和备用模型",
        "模型任务配置：不同AI任务的模型偏好",
        "通知设置：站内通知偏好；外部通知仍未接入",
        "数据源状态：最后更新时间、当前同步状态、来源和失败提示",
        ...(user?.role === "admin" ? ["管理员账户管理与发布运行状态：仅管理员可见"] : [])
      ]}
      extra={
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <ShieldCheck className="h-4 w-4 text-blue-700" />
              移动端更多
            </div>
            <p className="text-sm leading-6 text-slate-600">
              当前页在移动端底部导航中显示为“更多”，集中展示设置入口、当前登录身份和发布状态说明。
            </p>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950 lg:col-span-2">
            <p className="font-semibold">生产发布边界</p>
            <p className="mt-2">
              未获授权的真实行情、自动交易、支付、社区、全网爬虫和外部通知默认关闭；普通用户不会看到内部运维错误详情。
            </p>
          </div>
          <Link
            href="/settings/ai"
            className="focus-ring rounded-lg border border-slate-200 bg-white p-4 hover:bg-slate-50"
          >
            <p className="text-sm font-semibold text-slate-950">AI接口配置</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              连接本地后端，新增、编辑、测试和删除用户自带 OpenAI Compatible 配置。
            </p>
          </Link>
          <Link
            href="/settings/notifications"
            className="focus-ring rounded-lg border border-slate-200 bg-white p-4 hover:bg-slate-50"
          >
            <p className="text-sm font-semibold text-slate-950">通知设置</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              查看站内通知偏好、外部通知未接入说明和免打扰时间。
            </p>
          </Link>
          <Link
            href="/settings/sources"
            className="focus-ring rounded-lg border border-slate-200 bg-white p-4 hover:bg-slate-50"
          >
            <p className="text-sm font-semibold text-slate-950">信息来源</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              查看外部来源注册、实验公告Provider和未来来源规划，不在前端修改功能开关。
            </p>
          </Link>
          {user?.role === "admin" ? (
            <Link
              href="/settings/operations"
              className="focus-ring rounded-lg border border-slate-200 bg-white p-4 hover:bg-slate-50"
            >
              <p className="text-sm font-semibold text-slate-950">发布运行状态</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                查看私人测试版功能矩阵、授权边界和最近任务失败提示的管理员只读入口。
              </p>
            </Link>
          ) : null}
          {user?.role === "admin" ? (
            <Link
              href="/settings/market-data"
              className="focus-ring rounded-lg border border-slate-200 bg-white p-4 hover:bg-slate-50"
            >
              <p className="text-sm font-semibold text-slate-950">行情数据</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                查看日级行情快照来源、授权状态、同步运行和管理员手动同步入口。
              </p>
            </Link>
          ) : null}
          {user?.role === "admin" ? (
            <Link
              href="/settings/security-master"
              className="focus-ring rounded-lg border border-slate-200 bg-white p-4 hover:bg-slate-50"
            >
              <p className="text-sm font-semibold text-slate-950">证券目录</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                查看 A 股证券主数据状态，并手动触发开发环境证券目录同步。
              </p>
            </Link>
          ) : null}
          {user ? (
            <button
              onClick={handleLogout}
              className="focus-ring flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-4 text-left hover:bg-slate-50"
              type="button"
            >
              <LogOut className="mt-0.5 h-4 w-4 text-slate-700" />
              <span>
                <span className="block text-sm font-semibold text-slate-950">退出当前账户</span>
                <span className="mt-2 block text-sm leading-6 text-slate-600">
                  当前后端登录用户：{user.display_name || user.username}
                </span>
              </span>
            </button>
          ) : null}
        </div>
      }
    />
  );
}
