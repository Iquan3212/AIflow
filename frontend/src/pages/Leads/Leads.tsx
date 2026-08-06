import { useEffect, useMemo, useState } from "react";
import api from "../../services/api";
import Layout from "../../components/dashboard/Layout";

import DashboardCards from "../../components/dashboard/DashboardCards";
import LeadsToolbar from "../../components/dashboard/LeadsToolbar";

import "./Leads.css";

interface Lead {
    id: string;
    name: string | null;
    phone: string | null;
    email: string | null;
    service_interested: string | null;
    budget: string | null;
    status: string;
    created_at: string;
}

export default function Leads() {
    const [leads, setLeads] = useState<Lead[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");

    useEffect(() => {
        api
            .get("/leads/")
            .then((res) => setLeads(res.data))
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const filteredLeads = useMemo(() => {
        return leads.filter((lead) =>
            [
                lead.name,
                lead.phone,
                lead.email,
                lead.service_interested,
                lead.budget,
            ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase()
                .includes(search.toLowerCase())
        );
    }, [leads, search]);

    if (loading) {
        return <h2>Loading...</h2>;
    }

    return (
        <Layout><div className="leads-container">

            <div className="page-title">
                <h1>Leads</h1>

                <p>
                    Manage and track all customer leads collected by your AI
                    assistant.
                </p>
            </div>

            <DashboardCards
                stats={{
                    today_chats: 248,
                    new_leads: 37,
                    appointments: 19,
                    revenue: 84000,
                }}
            />

            <div style={{ marginTop: "30px" }} />

            <LeadsToolbar
                search={search}
                setSearch={setSearch}
            />

            <table className="leads-table">

                <thead>

                    <tr>

                        <th>Name</th>

                        <th>Phone</th>

                        <th>Email</th>

                        <th>Service</th>

                        <th>Budget</th>

                        <th>Status</th>

                    </tr>

                </thead>

                <tbody>

                    {filteredLeads.map((lead) => (

                        <tr key={lead.id}>

                            <td>{lead.name ?? "-"}</td>

                            <td>{lead.phone ?? "-"}</td>

                            <td>{lead.email ?? "-"}</td>

                            <td>{lead.service_interested ?? "-"}</td>

                            <td>{lead.budget ?? "-"}</td>

                            <td>
                                <span className={`status ${lead.status}`}>
                                    {lead.status}
                                </span>
                            </td>

                        </tr>

                    ))}

                    {filteredLeads.length === 0 && (
                        <tr>
                            <td
                                colSpan={6}
                                style={{
                                    textAlign: "center",
                                    padding: "40px",
                                }}
                            >
                                No leads found
                            </td>
                        </tr>
                    )}

                </tbody>

            </table>

        </div></Layout>
    );
}
