interface LogoProps {
    variant?: "dark" | "light";
    size?: "sm" | "md" | "lg";
    wordmark?: boolean;
}

const SIZE_MAP = {
    sm: { icon: 24, text: "text-base" },
    md: { icon: 30, text: "text-xl" },
    lg: { icon: 38, text: "text-2xl" },
};

/** Shared AIFlow mark: a simplified version of the bolt in public/favicon.svg,
 * so the browser tab icon and every in-app instance of the logo are the same
 * brand, not two different marks. */
export default function Logo({ variant = "dark", size = "md", wordmark = true }: LogoProps) {
    const { icon, text } = SIZE_MAP[size];
    const textColor = variant === "light" ? "text-white" : "text-ink-900";

    return (
        <span className="inline-flex items-center gap-2.5 select-none">
            <svg width={icon} height={icon} viewBox="0 0 48 46" fill="none" aria-hidden="true">
                <path
                    d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z"
                    fill="url(#aiflow-logo-gradient)"
                />
                <defs>
                    <linearGradient id="aiflow-logo-gradient" x1="0" y1="0" x2="48" y2="46" gradientUnits="userSpaceOnUse">
                        <stop stopColor="#5a8770" />
                        <stop offset="1" stopColor="#204133" />
                    </linearGradient>
                </defs>
            </svg>
            {wordmark && (
                <span className={`font-display font-bold tracking-tight ${text} ${textColor}`}>AIFlow</span>
            )}
        </span>
    );
}
