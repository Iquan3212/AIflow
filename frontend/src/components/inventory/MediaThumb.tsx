import { Building2, FileText, Image as ImageIcon } from "lucide-react";

import { useMediaBlobUrl } from "../../hooks/useMediaBlobUrl";
import type { PropertyMedia } from "../../types/inventory";

interface MediaThumbProps {
    media: PropertyMedia | null | undefined;
    fetcher: (media: PropertyMedia) => Promise<Blob>;
    className?: string;
    fallbackIcon?: "project" | "image";
}

/** A single cover/thumbnail image, or a neutral placeholder when there's
 * no media yet — used on cards where showing "no photo" plainly reads
 * better than a broken image icon. */
export default function MediaThumb({ media, fetcher, className = "", fallbackIcon = "image" }: MediaThumbProps) {
    const url = useMediaBlobUrl(
        () => (media ? fetcher(media) : Promise.reject()),
        [media?.id]
    );

    if (!media) {
        const Icon = fallbackIcon === "project" ? Building2 : ImageIcon;
        return (
            <div className={`flex items-center justify-center bg-slate-100 text-slate-300 ${className}`}>
                <Icon size={28} aria-hidden="true" />
            </div>
        );
    }

    if (media.media_type === "floor_plan" && media.file_type === "pdf") {
        return (
            <div className={`flex items-center justify-center bg-slate-100 text-slate-400 ${className}`}>
                <FileText size={28} aria-hidden="true" />
            </div>
        );
    }

    if (!url) {
        return <div className={`bg-slate-100 animate-pulse ${className}`} />;
    }

    return <img src={url} alt={media.filename} className={`object-cover ${className}`} />;
}
