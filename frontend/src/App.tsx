import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Landing from "./pages/Landing/Landing";
import Login from "./pages/Login/Login";
import Register from "./pages/Register/Register";
import Dashboard from "./pages/Dashboard/Dashboard";
import Conversations from "./pages/Conversations/Conversations";
import Leads from "./pages/Leads/Leads";
import Appointments from "./pages/Appointments/Appointments";
import Analytics from "./pages/Analytics/Analytics";
import Settings from "./pages/Settings/Settings";
import Drafts from "./pages/Drafts/Drafts";
import Support from "./pages/Support/Support";
import Knowledge from "./pages/Knowledge/Knowledge";
import Workflows from "./pages/Workflows/Workflows";

import ProtectedLayout from "./layouts/ProtectedLayout";
import PublicOnlyLayout from "./layouts/PublicOnlyLayout";
import BuyerProtectedLayout from "./layouts/BuyerProtectedLayout";
import BuyerPublicOnlyLayout from "./layouts/BuyerPublicOnlyLayout";
import Manager from "./pages/Manager/Manager";
import WorkforceUI from "./pages/Workforce/WorkforceUI";
import Discover from "./pages/Discover/Discover";
import BuyerLogin from "./pages/Buyer/BuyerLogin";
import BuyerRegister from "./pages/Buyer/BuyerRegister";
import BuyerHome from "./pages/Buyer/BuyerHome";

export default function App() {
    return (
        <BrowserRouter>
            <Routes>

                {/* Public routes — redirect to /dashboard if already signed in */}
                <Route element={<PublicOnlyLayout />}>
                    <Route path="/" element={<Landing />} />
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Register />} />
                </Route>

                {/* Buyer marketplace — genuinely separate auth/session from the
                    agency dashboard above (see BuyerAuthContext), so an agency
                    session never grants buyer routes or vice versa. */}
                <Route path="/discover" element={<Discover />} />
                <Route element={<BuyerPublicOnlyLayout />}>
                    <Route path="/buyer/login" element={<BuyerLogin />} />
                    <Route path="/buyer/register" element={<BuyerRegister />} />
                </Route>
                <Route element={<BuyerProtectedLayout />}>
                    <Route path="/buyer/home" element={<BuyerHome />} />
                </Route>

                {/* Protected routes — redirect to /login if signed out */}
                <Route element={<ProtectedLayout />}>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/conversations" element={<Conversations />} />
                    <Route path="/leads" element={<Leads />} />
                    <Route path="/appointments" element={<Appointments />} />
                    <Route path="/manager" element={<Manager />} />
                    <Route path="/workforce" element={<WorkforceUI />} />
                    <Route path="/drafts" element={<Drafts />} />
                    <Route path="/support" element={<Support />} />
                    <Route path="/knowledge" element={<Knowledge />} />
                    <Route path="/workflows" element={<Workflows />} />
                    <Route path="/analytics" element={<Analytics />} />
                    <Route path="/settings" element={<Settings />} />
                </Route>

                {/* Anything else falls back to the dashboard (or login, via ProtectedLayout) */}
                <Route path="*" element={<Navigate to="/dashboard" replace />} />

            </Routes>
        </BrowserRouter>
    );
}
