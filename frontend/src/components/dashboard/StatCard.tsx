import "./StatCard.css";
import type { ReactNode } from "react";

interface StatCardProps {
    title: string;
    value: string | number;
    icon: ReactNode;
    color: string;
    subtitle?: string;
}

export default function StatCard({
    title,
    value,
    icon,
    color,
    subtitle,
}: StatCardProps) {
    return (
        <div className="stat-card">

            <div
                className="stat-icon"
                style={{ background: color }}
            >
                {icon}
            </div>

            <div className="stat-content">

                <p>{title}</p>

                <h2>{value}</h2>

                {subtitle && (
                    <span>{subtitle}</span>
                )}

            </div>

        </div>
    );
}