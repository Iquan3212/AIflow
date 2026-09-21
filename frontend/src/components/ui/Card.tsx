import { forwardRef } from "react";
import type { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
    interactive?: boolean;
    /** Lifts on hover with a subtle 3D tilt — for property-adjacent
     * surfaces (cards you'd actually pick up and look at), not every
     * card in the product. Implies `interactive`. */
    depth?: boolean;
}

const Card = forwardRef<HTMLDivElement, CardProps>(
    ({ className = "", interactive = false, depth = false, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={`bg-white rounded-2xl border border-slate-200/70 shadow-soft ${
                    depth
                        ? "tilt-card hover:shadow-lifted hover:border-slate-300/80"
                        : interactive
                          ? "transition-all duration-200 hover:shadow-card hover:border-slate-300"
                          : ""
                } ${className}`}
                {...props}
            />
        );
    }
);
Card.displayName = "Card";

export default Card;
