import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Login from "./pages/Login/Login";
import Register from "./pages/Register/Register";
import Dashboard from "./pages/Dashboard/Dashboard";
import Conversations from "./pages/Conversations/Conversations";
import Leads from "./pages/Leads/Leads";
import Appointments from "./pages/Appointments/Appointments";
import Analytics from "./pages/Analytics/Analytics";
import Settings from "./pages/Settings/Settings";
import Drafts from "./pages/Drafts/Drafts";

import ProtectedLayout from "./layouts/ProtectedLayout";
import Manager from "./pages/Manager/Manager";
import WorkforceUI from "./pages/Workforce/WorkforceUI";

export default function App() {
    return (
        <BrowserRouter>
            <Routes>

                {/* Public routes */}
                <Route path="/" element={<Login />} />
                <Route path="/register" element={<Register />} />

                {/* Protected routes */}
                <Route element={<ProtectedLayout />}>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/conversations" element={<Conversations />} />
                    <Route path="/leads" element={<Leads />} />
                    <Route path="/appointments" element={<Appointments />} />
                    <Route path="/manager" element={<Manager />} />
                    <Route path="/workforce" element={<WorkforceUI />} />
                    <Route path="/drafts" element={<Drafts />} />
                    <Route path="/analytics" element={<Analytics />} />
                    <Route path="/settings" element={<Settings />} />
                </Route>

                {/* Anything else falls back to the dashboard (or login, via ProtectedLayout) */}
                <Route path="*" element={<Navigate to="/dashboard" replace />} />

            </Routes>
        </BrowserRouter>
    );
}
