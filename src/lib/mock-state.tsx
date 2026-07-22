"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode
} from "react";

import { getScenarioData } from "@/mock/data/scenarios";
import type { GeniusMockData, MockRole, ScenarioId, Stock } from "@/mock/types";

interface MockStateContextValue {
  scenarioId: ScenarioId;
  role: MockRole;
  data: GeniusMockData;
  setScenario: (scenarioId: ScenarioId) => void;
  setRole: (role: MockRole) => void;
  findStock: (stockId: string) => Stock | undefined;
}

const MockStateContext = createContext<MockStateContextValue | null>(null);

export function MockStateProvider({ children }: { children: ReactNode }) {
  const [scenarioId, setScenarioId] = useState<ScenarioId>("normal");
  const [role, setRoleState] = useState<MockRole>("user");

  const setScenario = useCallback((nextScenarioId: ScenarioId) => {
    setScenarioId(nextScenarioId);
    if (nextScenarioId === "admin") {
      setRoleState("admin");
    }
  }, []);

  const data = useMemo(() => getScenarioData(scenarioId), [scenarioId]);

  const setRole = useCallback((nextRole: MockRole) => {
    setRoleState(nextRole);
  }, []);

  const findStock = useCallback(
    (stockId: string) => data.stocks.find((stock) => stock.id === stockId),
    [data.stocks]
  );

  const value = useMemo(
    () => ({
      scenarioId,
      role,
      data,
      setScenario,
      setRole,
      findStock
    }),
    [data, findStock, role, scenarioId, setRole, setScenario]
  );

  return (
    <MockStateContext.Provider value={value}>
      {children}
    </MockStateContext.Provider>
  );
}

export function useMockState() {
  const context = useContext(MockStateContext);

  if (!context) {
    throw new Error("useMockState must be used within MockStateProvider");
  }

  return context;
}
