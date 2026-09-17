import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

// Client-only: the comparison feature reads full property records via
// the existing GET /marketplace/properties/{id} (already public, already
// returns everything the compare table needs) - no backend addition, no
// invented comparison fields. This context only ever stores which
// property ids are selected, persisted so a buyer's in-progress
// comparison survives a refresh or navigating away and back.

const STORAGE_KEY = "aiflow.compare_property_ids";
export const MAX_COMPARE = 4;

interface CompareContextType {
    ids: string[];
    isSelected: (id: string) => boolean;
    toggle: (id: string) => void;
    remove: (id: string) => void;
    clear: () => void;
    isFull: boolean;
}

const CompareContext = createContext<CompareContextType>({
    ids: [],
    isSelected: () => false,
    toggle: () => {},
    remove: () => {},
    clear: () => {},
    isFull: false,
});

function readStored(): string[] {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.filter((v) => typeof v === "string") : [];
    } catch {
        return [];
    }
}

export function CompareProvider({ children }: { children: ReactNode }) {
    const [ids, setIds] = useState<string[]>(() => readStored());

    useEffect(() => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
        } catch {
            // Best-effort persistence only - compare still works for this
            // session even if localStorage is unavailable (private mode, etc).
        }
    }, [ids]);

    const toggle = useCallback((id: string) => {
        setIds((current) => {
            if (current.includes(id)) return current.filter((i) => i !== id);
            if (current.length >= MAX_COMPARE) return current;
            return [...current, id];
        });
    }, []);

    const remove = useCallback((id: string) => {
        setIds((current) => current.filter((i) => i !== id));
    }, []);

    const clear = useCallback(() => setIds([]), []);

    const value = useMemo<CompareContextType>(
        () => ({
            ids,
            isSelected: (id: string) => ids.includes(id),
            toggle,
            remove,
            clear,
            isFull: ids.length >= MAX_COMPARE,
        }),
        [ids, toggle, remove, clear]
    );

    return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}

export const useCompare = () => useContext(CompareContext);
