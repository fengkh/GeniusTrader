import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";

export function PlaceholderPage({
  eyebrow,
  title,
  description,
  items,
  extra
}: {
  eyebrow: string;
  title: string;
  description: string;
  items: string[];
  extra?: ReactNode;
}) {
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-sm font-semibold text-slate-950">下一阶段计划承载</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {items.map((item) => (
            <div key={item} className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
              {item}
            </div>
          ))}
        </div>
        {extra ? <div className="mt-5">{extra}</div> : null}
        <Link
          href="/today"
          className="focus-ring mt-5 inline-flex h-10 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          <ArrowLeft className="h-4 w-4" />
          返回今日页
        </Link>
      </section>
    </div>
  );
}
