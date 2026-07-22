"use client";

import { UserCog } from "lucide-react";

import { useMockState } from "@/lib/mock-state";
import type { MockRole } from "@/mock/types";

export function MockRoleSwitcher({ compact = false }: { compact?: boolean }) {
  const { role, setRole } = useMockState();

  return (
    <label className="block">
      {!compact ? (
        <span className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-slate-600">
          <UserCog className="h-3.5 w-3.5 text-blue-700" />
          Mock身份
        </span>
      ) : null}
      <select
        value={role}
        onChange={(event) => setRole(event.target.value as MockRole)}
        className="focus-ring h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-800"
      >
        <option value="user">普通用户</option>
        <option value="admin">管理员</option>
      </select>
      {!compact ? (
        <p className="mt-1 text-xs leading-5 text-slate-500">
          身份切换只用于页面展示，不构成真实认证或权限实现。
        </p>
      ) : null}
    </label>
  );
}
