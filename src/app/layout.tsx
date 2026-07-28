import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/auth/AuthProvider";
import { AppShell } from "@/components/layout/AppShell";
import { APP_NAME, MOCK_DISCLOSURE } from "@/lib/constants";
import { MockStateProvider } from "@/lib/mock-state";

import "./globals.css";

export const metadata: Metadata = {
  title: `${APP_NAME} 私人测试版`,
  description: MOCK_DISCLOSURE
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <MockStateProvider>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </MockStateProvider>
      </body>
    </html>
  );
}
