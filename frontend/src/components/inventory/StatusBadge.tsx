import Badge, { type BadgeTone } from "../ui/Badge";
import type { ProjectStatus, PropertyStatus } from "../../types/inventory";

const PROPERTY_STATUS_META: Record<PropertyStatus, { label: string; tone: BadgeTone }> = {
    draft: { label: "Draft", tone: "neutral" },
    active: { label: "Active", tone: "success" },
    reserved: { label: "Reserved", tone: "warning" },
    blocked: { label: "Blocked", tone: "danger" },
    sold: { label: "Sold", tone: "info" },
    deactivated: { label: "Deactivated", tone: "neutral" },
    archived: { label: "Archived", tone: "neutral" },
};

const PROJECT_STATUS_META: Record<ProjectStatus, { label: string; tone: BadgeTone }> = {
    draft: { label: "Draft", tone: "neutral" },
    active: { label: "Active", tone: "success" },
    archived: { label: "Archived", tone: "neutral" },
};

export function PropertyStatusBadge({ status, className }: { status: PropertyStatus; className?: string }) {
    const meta = PROPERTY_STATUS_META[status];
    return <Badge tone={meta.tone} className={className}>{meta.label}</Badge>;
}

export function ProjectStatusBadge({ status, className }: { status: ProjectStatus; className?: string }) {
    const meta = PROJECT_STATUS_META[status];
    return <Badge tone={meta.tone} className={className}>{meta.label}</Badge>;
}
