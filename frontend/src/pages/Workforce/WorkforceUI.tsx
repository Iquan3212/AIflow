import React from "react";
import Layout from "../../components/dashboard/Layout";
import { useWorkforce } from "../../hooks/useWorkforce";
import EmployeeCard from "../../components/ai/EmployeeCard";
import AIHealthCard from "../../components/ai/AIHealthCard";

export default function WorkforceUI() {
  const { employees, loading } = useWorkforce(0);

  return (
    <Layout>
      <div className="max-w-6xl mx-auto">
        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-2xl bg-blue-600 text-white p-3">WF</div>
          <div>
            <h1 className="text-3xl font-bold">AI Workforce</h1>
            <p className="text-slate-500">Overview of all AI employees</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
            {loading && <div>Loading…</div>}
            {employees?.map((e) => <EmployeeCard key={e.id} employee={e} />)}
          </div>
          <div className="space-y-4">
            <AIHealthCard healthy={true} uptime="99.9%" notes="All systems nominal" />
          </div>
        </div>
      </div>
    </Layout>
  );
}