import { useEffect, useState } from "react";

import Layout from "../../components/dashboard/Layout";
import Hero from "../../components/dashboard/Hero";
import AIHealth from "../../components/dashboard/AIHealth";
import DashboardCards from "../../components/dashboard/DashboardCards";
import AnalyticsChart from "../../components/dashboard/AnalyticsChart";
import QuickActions from "../../components/dashboard/QuickActions";
import RecentConversations from "../../components/dashboard/RecentConversations";
import LeadPipeline from "../../components/dashboard/LeadPipeline";
import ActivityFeed from "../../components/dashboard/ActivityFeed";

import { getDashboardStats } from "../../services/dashboard";

export default function Dashboard() {
    const [stats, setStats] = useState<any>(null);

    useEffect(() => {
        async function loadDashboard() {
            try {
                const data = await getDashboardStats();
                setStats(data);
            } catch (error) {
                console.error("Failed to load dashboard:", error);
            }
        }

        loadDashboard();
    }, []);

    if (!stats) {
        return (
            <div className="flex items-center justify-center h-screen text-xl">
                Loading Dashboard...
            </div>
        );
    }

    return (
        <Layout>
            <Hero />

            <div className="mt-8">
                <AIHealth
                    model={stats.model}
                    responseTime={stats.response_time}
                    accuracy={stats.accuracy}
                />
            </div>

            <div className="mt-8">
                <DashboardCards stats={stats} />
            </div>

            <div className="grid grid-cols-2 gap-8 mt-8">
                <AnalyticsChart />
                <QuickActions />
            </div>

            <div className="grid grid-cols-3 gap-8 mt-8">
                <RecentConversations />
                <LeadPipeline />
                <ActivityFeed />
            </div>
        </Layout>
    );
}
