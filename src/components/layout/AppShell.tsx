"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { DesktopNav } from "@/components/navigation/DesktopNav";
import { MobileNav } from "@/components/navigation/MobileNav";
import { TopBar } from "@/components/layout/TopBar";
import { MOCK_DISCLOSURE } from "@/lib/constants";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";

  if (isLogin) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <DesktopNav />
      <div className="lg:pl-72">
        <TopBar />
        <main className="mx-auto max-w-7xl px-4 py-5 pb-24 lg:px-6 lg:pb-8">
          {children}
        </main>
        <MobileNav />
      </div>
      <div className="sr-only">{MOCK_DISCLOSURE}</div>
    </div>
  );
}
