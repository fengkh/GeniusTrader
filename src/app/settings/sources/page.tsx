"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, ExternalLink, ShieldAlert } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import {
  listAnnouncementProviders,
  listExternalSources,
  listFutureSourceGroups
} from "@/lib/api/external-sources";
import type {
  AnnouncementProvider,
  ExternalSource,
  FutureSourceGroup
} from "@/lib/api/types";

const EXPERIMENTAL_NOTICE =
  "当前公告同步功能处于实验阶段，数据来源、完整性、及时性、稳定性及使用授权尚未最终确认。";

export default function SourceSettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [sources, setSources] = useState<ExternalSource[]>([]);
  const [providers, setProviders] = useState<AnnouncementProvider[]>([]);
  const [futureGroups, setFutureGroups] = useState<FutureSourceGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || !user) {
      return;
    }
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [sourceRows, providerRows, futureRows] = await Promise.all([
          listExternalSources({ experimental: true }),
          listAnnouncementProviders(),
          listFutureSourceGroups()
        ]);
        if (!cancelled) {
          setSources(sourceRows);
          setProviders(providerRows);
          setFutureGroups(futureRows);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(humanizeApiError(caught));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [authLoading, user]);

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="信息来源注册状态属于后端受控配置，请先登录查看。"
        action={
          <Link
            href="/login?redirect=/settings/sources"
            className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
          >
            去登录
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="设置"
        title="信息来源"
        description="只读展示外部来源注册、实验公告 Provider 和未来来源规划。普通用户不能在本页修改来源启用状态。"
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

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <div className="flex gap-2">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <p>{EXPERIMENTAL_NOTICE} 功能开关仍由后端配置和来源注册状态共同控制。</p>
        </div>
      </section>

      {error ? <ErrorState title="来源信息加载失败" description={error} /> : null}
      {loading ? <LoadingSkeleton lines={8} /> : null}

      {!loading ? (
        <>
          <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-4 py-3">
              <h2 className="text-base font-semibold text-slate-950">已实现实验来源</h2>
              <p className="mt-1 text-sm text-slate-500">本阶段仅包含上市公司公告实验来源。</p>
            </div>
            <div className="divide-y divide-slate-100">
              {sources.map((source) => (
                <SourceRow key={source.id} source={source} />
              ))}
              {sources.length === 0 ? (
                <div className="p-4 text-sm text-slate-500">暂无可展示来源。</div>
              ) : null}
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-base font-semibold text-slate-950">公告 Provider 能力</h2>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {providers.map((provider) => (
                <article key={provider.source_code} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-slate-950">{provider.source_code}</p>
                    <Pill tone={provider.implemented ? "blue" : "slate"}>
                      {provider.implemented ? "已实现接口" : "未实现"}
                    </Pill>
                    <Pill tone={provider.enabled_by_config ? "emerald" : "amber"}>
                      {provider.enabled_by_config ? "配置已启用" : "配置关闭"}
                    </Pill>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">Adapter：{provider.provider_adapter}</p>
                  <p className="mt-1 text-sm text-slate-600">
                    能力：{provider.capabilities.length ? provider.capabilities.join("、") : "暂无可同步能力"}
                  </p>
                  <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-500">
                    {provider.limitations.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-base font-semibold text-slate-950">未来来源规划</h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              以下只表示未来评估方向，当前没有自动同步、没有授权状态，也不会写入公告表。
            </p>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {futureGroups.map((group) => (
                <article key={group.group} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-sm font-semibold text-slate-950">{group.group}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{group.examples.join("、")}</p>
                  <p className="mt-2 text-xs font-medium text-amber-800">{group.status}</p>
                </article>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function SourceRow({ source }: { source: ExternalSource }) {
  return (
    <article className="grid gap-3 p-4 lg:grid-cols-[1fr_160px_160px_180px] lg:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-950">{source.display_name}</h2>
          <Pill tone="blue">{source.source_code}</Pill>
          <Pill tone={source.experimental ? "amber" : "slate"}>{source.experimental ? "实验" : "正式"}</Pill>
          <Pill tone={source.enabled ? "emerald" : "slate"}>{source.enabled ? "已启用" : "未启用"}</Pill>
        </div>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          {source.publisher_name} · {source.source_category} · {source.access_mode}
        </p>
        {source.official_domain ? (
          <a
            href={`https://${source.official_domain}`}
            target="_blank"
            rel="noreferrer"
            className="focus-ring mt-1 inline-flex items-center gap-1 text-xs font-medium text-blue-700 hover:text-blue-800"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            {source.official_domain}
          </a>
        ) : null}
      </div>
      <Metric label="权威层级" value={`${source.authority_level} / ${source.source_tier.toUpperCase()}`} />
      <Metric label="健康状态" value={source.health_status} />
      <div className="text-xs leading-5 text-slate-600">
        <p>授权：{source.authorization_status}</p>
        <p>再展示：{source.redistribution_status}</p>
        <p>商业使用：{source.commercial_use_status}</p>
        <p>法律复核：{source.legal_review_status}</p>
      </div>
      {source.limitations.length > 0 ? (
        <p className="lg:col-span-4 text-xs leading-5 text-slate-500">{source.limitations.join("；")}</p>
      ) : null}
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function Pill({ children, tone = "slate" }: { children: string; tone?: "slate" | "blue" | "amber" | "emerald" }) {
  const tones = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    blue: "border-blue-200 bg-blue-50 text-blue-800",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-800"
  };
  return <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}>{children}</span>;
}
