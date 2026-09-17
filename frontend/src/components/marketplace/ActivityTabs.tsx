import { NavLink } from "react-router-dom";

const TABS = [
    { to: "/buyer/activity", label: "Overview", end: true },
    { to: "/buyer/inquiries", label: "Inquiries", end: false },
    { to: "/buyer/site-visits", label: "Site Visits", end: false },
    { to: "/buyer/bookings", label: "Bookings", end: false },
];

/** Shared sub-navigation across the four "My Activity" screens - each is
 * its own real, directly linkable route (per the routes spec), but they
 * read as one connected section rather than four disconnected pages. */
export default function ActivityTabs() {
    return (
        <nav aria-label="My Activity sections" className="flex items-center gap-1 border-b border-slate-200/70 mb-7 -mt-1 overflow-x-auto">
            {TABS.map((tab) => (
                <NavLink
                    key={tab.to}
                    to={tab.to}
                    end={tab.end}
                    className={({ isActive }) =>
                        `px-3.5 py-2.5 text-sm font-medium border-b-2 -mb-px whitespace-nowrap transition-colors ${
                            isActive
                                ? "border-brand-600 text-ink-950"
                                : "border-transparent text-slate-500 hover:text-ink-950"
                        }`
                    }
                >
                    {tab.label}
                </NavLink>
            ))}
        </nav>
    );
}
