"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { MOBILE_NAV_ITEMS } from "@/lib/constants";

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 grid h-16 grid-cols-5 border-t border-slate-200 bg-white lg:hidden">
      {MOBILE_NAV_ITEMS.map((item) => {
        const isActive =
          pathname === item.href || (item.href !== "/today" && pathname.startsWith(item.href));
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            className={`focus-ring flex flex-col items-center justify-center gap-1 text-xs font-medium ${
              isActive ? "text-slate-950" : "text-slate-500"
            }`}
          >
            <Icon className="h-4 w-4" />
            <span>{item.shortLabel ?? item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
