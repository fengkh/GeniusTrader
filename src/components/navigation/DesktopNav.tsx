"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { MockRoleSwitcher } from "@/components/mock/MockRoleSwitcher";
import { MockScenarioSwitcher } from "@/components/mock/MockScenarioSwitcher";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { APP_NAME, DESKTOP_NAV_ITEMS } from "@/lib/constants";

export function DesktopNav() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-slate-200 bg-white lg:flex lg:flex-col">
      <div className="border-b border-slate-200 px-5 py-5">
        <div className="text-lg font-semibold text-slate-950">{APP_NAME}</div>
        <p className="mt-1 text-xs text-slate-500">私人测试版 Mock 原型</p>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {DESKTOP_NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href || (item.href !== "/today" && pathname.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`focus-ring flex h-11 items-center gap-3 rounded-md px-3 text-sm font-medium ${
                isActive
                  ? "bg-slate-900 text-white"
                  : "text-slate-700 hover:bg-slate-100 hover:text-slate-950"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="space-y-4 border-t border-slate-200 p-4">
        <MockRoleSwitcher />
        <MockScenarioSwitcher />
        <SimulatedDataBadge />
      </div>
    </aside>
  );
}
