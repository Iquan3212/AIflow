import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";

import Button from "../ui/Button";

/** The one shared "you need a higher plan for this" surface - shown, not
 * hidden: the feature stays visible/discoverable, with an honest
 * explanation and a direct path to upgrade, rather than disappearing
 * with no explanation. */
export default function UpgradePrompt({
    message,
    planName,
}: {
    message: string;
    /** e.g. "Professional" - only shown when the caller knows exactly
     * which plan unlocks this. */
    planName?: string;
}) {
    return (
        <div className="flex items-center gap-3 bg-flare-50 border border-flare-300/60 rounded-xl p-4">
            <div className="w-9 h-9 rounded-lg bg-flare-500/20 text-flare-600 flex items-center justify-center shrink-0">
                <Sparkles size={16} aria-hidden="true" />
            </div>
            <p className="text-sm text-ink-950 flex-1">
                {message}
                {planName && <> — available on <strong>{planName}</strong>.</>}
            </p>
            <Link to="/pricing" className="shrink-0">
                <Button size="sm" variant="flare">Upgrade</Button>
            </Link>
        </div>
    );
}
