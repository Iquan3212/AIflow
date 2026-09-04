import { useEffect } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

export default function Modal({
    title,
    onClose,
    children,
}: {
    title: string;
    onClose: () => void;
    children: ReactNode;
}) {
    useEffect(() => {
        function handleKey(e: KeyboardEvent) {
            if (e.key === "Escape") onClose();
        }
        document.addEventListener("keydown", handleKey);
        return () => document.removeEventListener("keydown", handleKey);
    }, [onClose]);

    return (
        <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-slate-900/50" onClick={onClose} aria-hidden="true" />
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="modal-title"
                className="relative bg-white rounded-xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto"
            >
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
                    <h2 id="modal-title" className="text-base font-semibold text-slate-900">
                        {title}
                    </h2>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label="Close dialog"
                        className="text-slate-400 hover:text-slate-600"
                    >
                        <X size={20} />
                    </button>
                </div>
                <div className="p-5">{children}</div>
            </div>
        </div>
    );
}
