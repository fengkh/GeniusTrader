import Link from "next/link";
import { LockKeyhole, ShieldCheck } from "lucide-react";

import { APP_NAME, MOCK_DISCLOSURE } from "@/lib/constants";

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-5xl items-center">
        <div className="grid w-full gap-6 lg:grid-cols-[1fr_420px] lg:items-center">
          <section className="space-y-5">
            <div className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800">
              <ShieldCheck className="h-4 w-4 text-blue-700" />
              私人测试版
            </div>
            <div>
              <h1 className="text-3xl font-semibold text-slate-950 md:text-4xl">
                {APP_NAME}
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
                A股自选股复盘与多源舆情管理平台。当前页面仅用于 Mock
                原型验证，不连接真实账户、数据库、行情、资讯或AI接口。
              </p>
            </div>
            <div className="grid gap-3 text-sm text-slate-700 sm:grid-cols-2">
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                账户由管理员创建，不开放公众注册。
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                临时密码首次登录后必须修改。
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                第一版不提供邮件找回密码。
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                身份切换仅用于演示，不构成真实认证。
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-slate-900 text-white">
                <LockKeyhole className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-950">登录原型</h2>
                <p className="text-sm text-slate-500">不会保存或校验输入内容</p>
              </div>
            </div>
            <form className="space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-slate-700">用户名</span>
                <input
                  className="focus-ring mt-1 h-11 w-full rounded-md border border-slate-300 px-3 text-sm"
                  placeholder="由管理员分配的账户"
                  type="text"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">密码</span>
                <input
                  className="focus-ring mt-1 h-11 w-full rounded-md border border-slate-300 px-3 text-sm"
                  placeholder="临时密码或已修改密码"
                  type="password"
                />
              </label>
              <button
                className="focus-ring h-11 w-full rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800"
                type="button"
              >
                登录
              </button>
              <Link
                href="/today"
                className="focus-ring flex h-11 w-full items-center justify-center rounded-md border border-blue-200 bg-blue-50 px-4 text-sm font-semibold text-blue-800 hover:bg-blue-100"
              >
                进入Mock演示
              </Link>
            </form>
            <p className="mt-5 rounded-md bg-slate-50 p-3 text-xs leading-5 text-slate-600">
              {MOCK_DISCLOSURE}
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
