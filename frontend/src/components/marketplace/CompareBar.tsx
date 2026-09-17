import { useNavigate } from "react-router-dom";
import { Scale, X } from "lucide-react";

import Button from "../ui/Button";
import { useCompare, MAX_COMPARE } from "../../context/CompareContext";

/** A floating bar that appears the moment a buyer selects a property to
 * compare, on any page that offers the compare toggle (Discover, Saved,
 * project detail). Lets them jump to the comparison or back out without
 * losing their place. */
export default function CompareBar() {
    const { ids, clear } = useCompare();
    const navigate = useNavigate();

    if (ids.length === 0) return null;

    return (
        <div className="fixed bottom-[4.5rem] lg:bottom-6 inset-x-0 z-20 flex justify-center px-4 pointer-events-none">
            <div className="pointer-events-auto bg-ink-950 text-white rounded-2xl shadow-lifted px-4 py-3 flex items-center gap-3 max-w-full">
                <Scale size={16} className="text-flare-400 shrink-0" aria-hidden="true" />
                <p className="text-sm font-medium whitespace-nowrap">
                    {ids.length} {ids.length === 1 ? "property" : "properties"} selected
                    <span className="text-slate-400"> · up to {MAX_COMPARE}</span>
                </p>
                <Button size="sm" variant="flare" onClick={() => navigate("/buyer/compare")}>
                    Compare
                </Button>
                <button
                    type="button"
                    onClick={clear}
                    aria-label="Clear comparison"
                    className="text-slate-400 hover:text-white rounded-full p-1.5 hover:bg-white/10 shrink-0"
                >
                    <X size={15} />
                </button>
            </div>
        </div>
    );
}
