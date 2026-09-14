import { useEffect, useState } from "react";

/** Every media endpoint requires a Bearer token (see api.ts's interceptor),
 * so a plain <img src="/properties/.../file"> can never authenticate — the
 * browser sends no Authorization header for it. This fetches the bytes
 * through the same authenticated axios client and hands back a local
 * blob: URL an <img>/<a> can use, revoking it on unmount/change so blob
 * URLs never accumulate across a long-lived session. */
export function useMediaBlobUrl(fetcher: () => Promise<Blob>, deps: unknown[]): string | null {
    const [url, setUrl] = useState<string | null>(null);

    useEffect(() => {
        let objectUrl: string | null = null;
        let cancelled = false;

        fetcher().then((blob) => {
            if (cancelled) return;
            objectUrl = URL.createObjectURL(blob);
            setUrl(objectUrl);
        }).catch(() => {
            if (!cancelled) setUrl(null);
        });

        return () => {
            cancelled = true;
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);

    return url;
}
