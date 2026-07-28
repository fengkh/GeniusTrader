"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AlertCircle, LockKeyhole, ShieldCheck } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { humanizeApiError } from "@/lib/api/errors";
import { APP_NAME, MOCK_DISCLOSURE } from "@/lib/constants";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [redirectPath, setRedirectPath] = useState("/today");

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      const redirect = params.get("redirect");
      if (redirect?.startsWith("/")) {
        setRedirectPath(redirect);
      }
      setExpired(params.get("expired") === "1");
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      setPassword("");
      router.push(redirectPath);
    } catch (caught) {
      setPassword("");
      setError(humanizeApiError(caught));
    } finally {
      setSubmitting(false);
    }
  }

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
                A股自选股复盘与多源舆情管理平台。本阶段登录接入本地后端 Session
                Cookie；行情、复盘和未联调页面仍保持 Mock。
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
                前端不保存 Session Token、密码或 AI API Key。
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-slate-900 text-white">
                <LockKeyhole className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-950">登录</h2>
                <p className="text-sm text-slate-500">使用管理员创建的私人测试账户</p>
              </div>
            </div>

            {expired ? (
              <div className="mb-4 flex gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                登录状态已过期，请重新登录。
              </div>
            ) : null}
            {error ? (
              <div className="mb-4 flex gap-2 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {error}
              </div>
            ) : null}

            <form className="space-y-4" onSubmit={handleSubmit}>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">用户名</span>
                <input
                  className="focus-ring mt-1 h-11 w-full rounded-md border border-slate-300 px-3 text-sm"
                  placeholder="由管理员分配的账户"
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  required
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">密码</span>
                <input
                  className="focus-ring mt-1 h-11 w-full rounded-md border border-slate-300 px-3 text-sm"
                  placeholder="临时密码或已修改密码"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </label>
              <button
                className="focus-ring h-11 w-full rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                type="submit"
                disabled={submitting}
              >
                {submitting ? "登录中..." : "登录"}
              </button>
              <Link
                href="/today"
                className="focus-ring flex h-11 w-full items-center justify-center rounded-md border border-blue-200 bg-blue-50 px-4 text-sm font-semibold text-blue-800 hover:bg-blue-100"
              >
                进入今日页
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
