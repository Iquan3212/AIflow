import React from "react";
import { BotIcon } from "lucide-react";
import EmployeeCard from "../../components/ai/EmployeeCard";
import Layout from "../../components/dashboard/Layout";
import { useEmployees } from "../../hooks/useEmployees";

export default function Workforce() {
    const { employees, loading } = useEmployees();

    return (
        <Layout>
            <div className="max-w-6xl mx-auto">
                <div className="mb-6 flex items-center gap-3">
                    <div className="rounded-2xl bg-blue-600 text-white p-3"><svg />{/* placeholder icon */}</div>
                    <div>
                        <h1 className="text-3xl font-bold">AI Workforce</h1>
                        <p className="text-slate-500">Monitor and manage your AI employees</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {loading && <div>Loading employees…</div>}
                    {employees && employees.map((emp) => (
                        <EmployeeCard key={emp.id} employee={emp} />
                    ))}
                </div>
            </div>
        </Layout>
    );
}
