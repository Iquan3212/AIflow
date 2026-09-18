import { useState } from "react";

import Button from "../ui/Button";
import UpgradePrompt from "../billing/UpgradePrompt";
import { getErrorMessage, isPlanLimitError } from "../../services/api";
import { ALLOWED_STATUS_TRANSITIONS } from "../../types/inventory";
import { PropertyStatusBadge } from "./StatusBadge";
import type { PropertyStatus } from "../../types/inventory";

/** Only ever offers a transition ALLOWED_STATUS_TRANSITIONS (mirrored
 * from app/services/inventory/status.py) actually allows from the
 * current status — e.g. a 'sold' unit only ever offers 'Archive', never
 * an "Active" button that would just 409 against the real backend
 * lifecycle. */
export default function StatusTransitionControl({
    status,
    onChange,
}: {
    status: PropertyStatus;
    onChange: (next: PropertyStatus) => Promise<void>;
}) {
    const [pending, setPending] = useState<PropertyStatus | null>(null);
    const [error, setError] = useState("");
    const [limitReached, setLimitReached] = useState(false);

    async function handleClick(next: PropertyStatus) {
        setPending(next);
        setError("");
        setLimitReached(false);
        try {
            await onChange(next);
        } catch (err) {
            if (isPlanLimitError(err)) {
                setLimitReached(true);
            }
            setError(getErrorMessage(err));
        } finally {
            setPending(null);
        }
    }

    const options = ALLOWED_STATUS_TRANSITIONS[status] ?? [];

    return (
        <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm text-slate-500">Status:</span>
                <PropertyStatusBadge status={status} />
                {options.map((next) => (
                    <Button
                        key={next}
                        size="sm"
                        variant="secondary"
                        loading={pending === next}
                        onClick={() => handleClick(next)}
                    >
                        Move to {next}
                    </Button>
                ))}
            </div>
            {error && (limitReached ? <UpgradePrompt message={error} /> : <p className="text-sm text-red-600">{error}</p>)}
        </div>
    );
}
