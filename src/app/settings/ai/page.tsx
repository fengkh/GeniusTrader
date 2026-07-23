"use client";

import Link from "next/link";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  FlaskConical,
  KeyRound,
  Pencil,
  Plus,
  RefreshCw,
  Trash2
} from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import {
  createAIProvider,
  deleteAIProvider,
  listAIProviders,
  testAIProvider,
  updateAIProvider
} from "@/lib/api/ai-providers";
import { humanizeApiError } from "@/lib/api/errors";
import type { AIProvider } from "@/lib/api/types";

interface ProviderFormState {
  providerName: string;
  baseUrl: string;
  modelName: string;
  apiKey: string;
  enabled: boolean;
  requestTimeoutSeconds: string;
  maxOutputTokens: string;
}

const emptyForm: ProviderFormState = {
  providerName: "",
  baseUrl: "",
  modelName: "",
  apiKey: "",
  enabled: true,
  requestTimeoutSeconds: "",
  maxOutputTokens: ""
};

export default function AISettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editing, setEditing] = useState<AIProvider | null>(null);
  const [form, setForm] = useState<ProviderFormState>(emptyForm);

  const enabledProvider = useMemo(
    () => providers.find((provider) => provider.enabled),
    [providers]
  );

  const refreshProviders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProviders(await listAIProviders());
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
      void refreshProviders();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [authLoading, refreshProviders, user]);

  function startCreate() {
    setEditing(null);
    setForm(emptyForm);
    setSuccess(null);
    setError(null);
  }

  function startEdit(provider: AIProvider) {
    setEditing(provider);
    setForm({
      providerName: provider.provider_name,
      baseUrl: provider.base_url,
      modelName: provider.model_name,
      apiKey: "",
      enabled: provider.enabled,
      requestTimeoutSeconds: provider.request_timeout_seconds?.toString() ?? "",
      maxOutputTokens: provider.max_output_tokens?.toString() ?? ""
    });
    setSuccess(null);
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (!editing && !form.apiKey.trim()) {
        setError("新增 AI 配置必须填写 API Key。");
        return;
      }

      const payload = {
        provider_name: form.providerName.trim(),
        base_url: form.baseUrl.trim(),
        model_name: form.modelName.trim(),
        enabled: form.enabled,
        request_timeout_seconds: optionalNumber(form.requestTimeoutSeconds),
        max_output_tokens: optionalNumber(form.maxOutputTokens)
      };

      if (editing) {
        await updateAIProvider(editing.id, {
          ...payload,
          ...(form.apiKey.trim() ? { api_key: form.apiKey } : {})
        });
        setSuccess("AI 配置已更新。");
      } else {
        await createAIProvider({ ...payload, api_key: form.apiKey });
        setSuccess("AI 配置已创建。");
      }

      setForm({ ...emptyForm, apiKey: "" });
      setEditing(null);
      await refreshProviders();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setForm((current) => ({ ...current, apiKey: "" }));
      setSaving(false);
    }
  }

  async function handleTest(provider: AIProvider) {
    setTestingId(provider.id);
    setError(null);
    setSuccess(null);
    try {
      const result = await testAIProvider(provider.id);
      await refreshProviders();
      setSuccess(
        result.status === "succeeded"
          ? "连接测试成功。"
          : `连接测试失败：${result.error_code ?? "未知错误"}`
      );
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setTestingId(null);
    }
  }

  async function handleDelete(provider: AIProvider) {
    if (!window.confirm(`确认删除 AI 配置“${provider.provider_name}”？此操作不会在前端读取 API Key。`)) {
      return;
    }
    setError(null);
    setSuccess(null);
    try {
      await deleteAIProvider(provider.id);
      setSuccess("AI 配置已删除。");
      await refreshProviders();
      if (editing?.id === provider.id) {
        startCreate();
      }
    } catch (caught) {
      setError(humanizeApiError(caught));
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="设置"
        title="AI接口配置"
        description="本页连接本地后端 API。用户 API Key 仅提交给后端加密保存，前端不会读取完整密钥，也不会直接调用第三方 AI。"
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

      {!user && !authLoading ? (
        <EmptyState
          title="需要登录"
          description="AI 配置属于用户私有数据，请先使用管理员创建的测试账户登录。"
          action={
            <Link
              href="/login?redirect=/settings/ai"
              className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
            >
              去登录
            </Link>
          }
        />
      ) : null}

      {error ? <ErrorState title="请求失败" description={error} /> : null}
      {success ? (
        <div className="flex gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          {success}
        </div>
      ) : null}

      {user ? (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">已配置 Provider</h2>
                <p className="mt-1 text-sm text-slate-500">
                  当前启用：{enabledProvider?.provider_name ?? "暂无启用配置"}
                </p>
              </div>
              <button
                onClick={refreshProviders}
                className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                type="button"
              >
                <RefreshCw className="h-4 w-4" />
                刷新
              </button>
            </div>

            <div className="mt-4">
              {loading ? (
                <LoadingSkeleton lines={5} />
              ) : providers.length === 0 ? (
                <EmptyState title="暂无 AI 配置" description="添加 OpenAI Compatible 配置后，信息结构化分析和后续复盘 AI 任务才可使用。" />
              ) : (
                <div className="space-y-3">
                  {providers.map((provider) => (
                    <article key={provider.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold text-slate-950">{provider.provider_name}</h3>
                            <span className={provider.enabled ? "rounded-md bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800" : "rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600"}>
                              {provider.enabled ? "已启用" : "未启用"}
                            </span>
                            <span className="rounded-md bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-800">
                              {provider.api_style}
                            </span>
                          </div>
                          <p className="mt-2 break-all text-sm text-slate-700">{provider.base_url}</p>
                          <p className="mt-1 text-sm text-slate-600">模型：{provider.model_name}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            Key 状态：{provider.api_key_masked ?? "未配置"}；最后测试：
                            {provider.last_test_status ?? "未测试"}
                            {provider.last_error_code ? `（${provider.last_error_code}）` : ""}
                          </p>
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-2">
                          <button
                            onClick={() => handleTest(provider)}
                            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 text-sm font-semibold text-blue-800 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                            type="button"
                            disabled={testingId === provider.id}
                          >
                            <FlaskConical className="h-4 w-4" />
                            {testingId === provider.id ? "测试中" : "测试"}
                          </button>
                          <button
                            onClick={() => startEdit(provider)}
                            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                            type="button"
                          >
                            <Pencil className="h-4 w-4" />
                            编辑
                          </button>
                          <button
                            onClick={() => handleDelete(provider)}
                            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-rose-200 bg-white px-3 text-sm font-semibold text-rose-700 hover:bg-rose-50"
                            type="button"
                          >
                            <Trash2 className="h-4 w-4" />
                            删除
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              {editing ? <Pencil className="h-5 w-5 text-slate-700" /> : <Plus className="h-5 w-5 text-slate-700" />}
              <h2 className="text-lg font-semibold text-slate-950">
                {editing ? "编辑 AI Provider" : "新增 AI Provider"}
              </h2>
            </div>
            <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
              <Field label="Provider 名称">
                <input
                  className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                  value={form.providerName}
                  onChange={(event) => setForm({ ...form, providerName: event.target.value })}
                  required
                  maxLength={100}
                />
              </Field>
              <Field label="Base URL">
                <input
                  className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                  value={form.baseUrl}
                  onChange={(event) => setForm({ ...form, baseUrl: event.target.value })}
                  placeholder="https://example.com/v1"
                  type="url"
                  required
                />
              </Field>
              <Field label="模型名称">
                <input
                  className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                  value={form.modelName}
                  onChange={(event) => setForm({ ...form, modelName: event.target.value })}
                  placeholder="例如 deepseek-chat 或用户自定义名称"
                  required
                  maxLength={120}
                />
              </Field>
              <Field label={editing ? "API Key（留空表示不更新）" : "API Key"}>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
                  <input
                    className="focus-ring h-10 w-full rounded-md border border-slate-300 pl-9 pr-3 text-sm"
                    value={form.apiKey}
                    onChange={(event) => setForm({ ...form, apiKey: event.target.value })}
                    type="password"
                    autoComplete="off"
                    required={!editing}
                  />
                </div>
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="超时秒数（可选）">
                  <input
                    className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                    value={form.requestTimeoutSeconds}
                    onChange={(event) => setForm({ ...form, requestTimeoutSeconds: event.target.value })}
                    type="number"
                    min={1}
                    max={120}
                  />
                </Field>
                <Field label="最大输出 Token（可选）">
                  <input
                    className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                    value={form.maxOutputTokens}
                    onChange={(event) => setForm({ ...form, maxOutputTokens: event.target.value })}
                    type="number"
                    min={1}
                    max={20000}
                  />
                </Field>
              </div>
              <label className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <span>启用为当前默认 Provider</span>
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
                  className="h-4 w-4 rounded border-slate-300"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                  type="submit"
                  disabled={saving}
                >
                  {saving ? "保存中..." : editing ? "保存修改" : "新增配置"}
                </button>
                {editing ? (
                  <button
                    onClick={startCreate}
                    className="focus-ring inline-flex h-10 items-center rounded-md border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                    type="button"
                  >
                    取消编辑
                  </button>
                ) : null}
              </div>
            </form>
            <p className="mt-4 rounded-md bg-slate-50 p-3 text-xs leading-5 text-slate-600">
              测试连接会由后端短暂解密密钥并调用用户配置的 Provider。本页不会展示完整密钥，不保存完整 Prompt 或第三方正文。
            </p>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}
