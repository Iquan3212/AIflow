import { useEffect, useState, useCallback } from "react";
import { getWorkforce } from "../services/workforce";
import { getErrorMessage } from "../services/api";
import type { EmployeeInfo } from "../types/ai";

export function useWorkforce(pollIntervalMs = 0) {
  const [employees, setEmployees] = useState<EmployeeInfo[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await getWorkforce();
      setEmployees(resp.employees || []);
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    if (pollIntervalMs > 0) {
      const timer = setInterval(() => {
        void load();
      }, pollIntervalMs);
      return () => clearInterval(timer);
    }
    return;
  }, [load, pollIntervalMs]);

  return { employees, loading, error, reload: load };
}