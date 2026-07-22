"use client";

import { FlaskConical } from "lucide-react";

import { SCENARIOS } from "@/lib/constants";
import { useMockState } from "@/lib/mock-state";
import type { ScenarioId } from "@/mock/types";

export function MockScenarioSwitcher({ compact = false }: { compact?: boolean }) {
  const { scenarioId, setScenario, data } = useMockState();

  return (
    <label className="block">
      {!compact ? (
        <span className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-slate-600">
          <FlaskConical className="h-3.5 w-3.5 text-blue-700" />
          Mock场景
        </span>
      ) : null}
      <select
        value={scenarioId}
        onChange={(event) => setScenario(event.target.value as ScenarioId)}
        className="focus-ring h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-800"
      >
        {SCENARIOS.map((scenario) => (
          <option key={scenario.id} value={scenario.id}>
            {scenario.name}
          </option>
        ))}
      </select>
      {!compact ? (
        <p className="mt-1 text-xs leading-5 text-slate-500">{data.scenarioDescription}</p>
      ) : null}
    </label>
  );
}
