import { useRef, useState } from "react";
import { FileText, Plus, Trash2 } from "lucide-react";

import Button from "../ui/Button";
import { getErrorMessage } from "../../services/api";
import MediaThumb from "./MediaThumb";
import type { PropertyMedia, PropertyMediaType } from "../../types/inventory";

interface MediaGalleryProps {
    media: PropertyMedia[];
    fetcher: (media: PropertyMedia) => Promise<Blob>;
    onUpload: (file: File, mediaType: PropertyMediaType) => Promise<void>;
    onDelete: (mediaId: string) => Promise<void>;
    /** Property media can be an image or a floor plan; project media is
     * always a cover image (see routers/projects.py's upload endpoint,
     * which hardcodes PropertyMediaType.image). */
    allowFloorPlan?: boolean;
}

export default function MediaGallery({ media, fetcher, onUpload, onDelete, allowFloorPlan = false }: MediaGalleryProps) {
    const imageInputRef = useRef<HTMLInputElement>(null);
    const floorPlanInputRef = useRef<HTMLInputElement>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    async function handleFile(file: File | undefined, mediaType: PropertyMediaType) {
        if (!file) return;
        setBusy(true);
        setError("");
        try {
            await onUpload(file, mediaType);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setBusy(false);
        }
    }

    async function handleDelete(mediaId: string) {
        if (!window.confirm("Delete this file?")) return;
        try {
            await onDelete(mediaId);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    return (
        <div className="space-y-3">
            {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg p-3 text-sm">{error}</div>}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                {media.map((item) => (
                    <div key={item.id} className="relative group rounded-xl overflow-hidden border border-slate-200/70">
                        <MediaThumb media={item} fetcher={fetcher} className="w-full h-28" />
                        {item.media_type === "floor_plan" && (
                            <span className="absolute bottom-1.5 left-1.5 bg-ink-950/80 text-white text-[10px] rounded px-1.5 py-0.5 flex items-center gap-1">
                                <FileText size={10} /> Floor plan
                            </span>
                        )}
                        <button
                            type="button"
                            onClick={() => handleDelete(item.id)}
                            aria-label="Delete file"
                            className="absolute top-1.5 right-1.5 bg-white/90 text-slate-500 rounded-lg p-1.5 opacity-0 group-hover:opacity-100 hover:text-red-600 transition-opacity"
                        >
                            <Trash2 size={13} />
                        </button>
                    </div>
                ))}

                <button
                    type="button"
                    onClick={() => imageInputRef.current?.click()}
                    disabled={busy}
                    className="flex flex-col items-center justify-center gap-1 h-28 rounded-xl border-2 border-dashed border-slate-200 text-slate-400 hover:border-brand-400 hover:text-brand-600 transition-colors disabled:opacity-50"
                >
                    <Plus size={18} />
                    <span className="text-xs font-medium">Add photo</span>
                </button>
                <input
                    ref={imageInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={(e) => {
                        void handleFile(e.target.files?.[0], "image");
                        e.target.value = "";
                    }}
                />

                {allowFloorPlan && (
                    <>
                        <button
                            type="button"
                            onClick={() => floorPlanInputRef.current?.click()}
                            disabled={busy}
                            className="flex flex-col items-center justify-center gap-1 h-28 rounded-xl border-2 border-dashed border-slate-200 text-slate-400 hover:border-brand-400 hover:text-brand-600 transition-colors disabled:opacity-50"
                        >
                            <FileText size={18} />
                            <span className="text-xs font-medium">Add floor plan</span>
                        </button>
                        <input
                            ref={floorPlanInputRef}
                            type="file"
                            accept="application/pdf,image/jpeg,image/png"
                            className="hidden"
                            onChange={(e) => {
                                void handleFile(e.target.files?.[0], "floor_plan");
                                e.target.value = "";
                            }}
                        />
                    </>
                )}
            </div>
            {busy && <Button variant="ghost" size="sm" loading disabled>Uploading…</Button>}
        </div>
    );
}
