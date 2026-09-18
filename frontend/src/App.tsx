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
import Inventory from "./pages/Inventory/Inventory";
import ProjectDetail from "./pages/Inventory/ProjectDetail";
import PropertyDetail from "./pages/Inventory/PropertyDetail";
import Bookings from "./pages/Bookings/Bookings";

import ProtectedLayout from "./layouts/ProtectedLayout";
import PublicOnlyLayout from "./layouts/PublicOnlyLayout";
import BuyerProtectedLayout from "./layouts/BuyerProtectedLayout";
import BuyerPublicOnlyLayout from "./layouts/BuyerPublicOnlyLayout";
import Manager from "./pages/Manager/Manager";
import WorkforceUI from "./pages/Workforce/WorkforceUI";
import Discover from "./pages/Discover/Discover";
import DiscoverProjectDetail from "./pages/Discover/ProjectDetail";
import DiscoverPropertyDetail from "./pages/Discover/PropertyDetail";
import BuyerLogin from "./pages/Buyer/BuyerLogin";
import BuyerRegister from "./pages/Buyer/BuyerRegister";
import BuyerHome from "./pages/Buyer/BuyerHome";
import BuyerSaved from "./pages/Buyer/BuyerSaved";
import BuyerCompare from "./pages/Buyer/BuyerCompare";
import BuyerActivity from "./pages/Buyer/BuyerActivity";
import BuyerInquiries from "./pages/Buyer/BuyerInquiries";
import BuyerSiteVisits from "./pages/Buyer/BuyerSiteVisits";
import BuyerBookings from "./pages/Buyer/BuyerBookings";
import BuyerAssistant from "./pages/Buyer/BuyerAssistant";
import BuyerProfile from "./pages/Buyer/BuyerProfile";
import Pricing from "./pages/Billing/Pricing";
import Billing from "./pages/Billing/Billing";
import NotFoundRedirect from "./layouts/NotFoundRedirect";

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
                    session never grants buyer routes or vice versa. Discover and
                    the AI Assistant stay public (no buyer session required to
                    browse or ask a question); everything under BuyerProtectedLayout
                    requires a signed-in buyer. */}
                <Route path="/discover" element={<Discover />} />
                <Route path="/discover/projects/:projectId" element={<DiscoverProjectDetail />} />
                <Route path="/discover/properties/:propertyId" element={<DiscoverPropertyDetail />} />
                <Route path="/buyer/assistant" element={<BuyerAssistant />} />
                <Route element={<BuyerPublicOnlyLayout />}>
                    <Route path="/buyer/login" element={<BuyerLogin />} />
                    <Route path="/buyer/register" element={<BuyerRegister />} />
                </Route>
                <Route element={<BuyerProtectedLayout />}>
                    <Route path="/buyer/home" element={<BuyerHome />} />
                    <Route path="/buyer/saved" element={<BuyerSaved />} />
                    <Route path="/buyer/compare" element={<BuyerCompare />} />
                    <Route path="/buyer/activity" element={<BuyerActivity />} />
                    <Route path="/buyer/inquiries" element={<BuyerInquiries />} />
                    <Route path="/buyer/site-visits" element={<BuyerSiteVisits />} />
                    <Route path="/buyer/bookings" element={<BuyerBookings />} />
                    <Route path="/buyer/profile" element={<BuyerProfile />} />
                    {/* No separate Settings screen - Notifications/Security live
                        as tabs inside Profile, so this is a redirect rather than
                        a second page with the same content. */}
                    <Route path="/buyer/settings" element={<Navigate to="/buyer/profile" replace />} />
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
                    <Route path="/inventory" element={<Inventory />} />
                    <Route path="/inventory/projects/:projectId" element={<ProjectDetail />} />
                    <Route path="/inventory/properties/:propertyId" element={<PropertyDetail />} />
                    <Route path="/bookings" element={<Bookings />} />
                    <Route path="/analytics" element={<Analytics />} />
                    <Route path="/pricing" element={<Pricing />} />
                    <Route path="/billing" element={<Billing />} />
                    <Route path="/settings" element={<Settings />} />
                </Route>

                {/* Anything else: a signed-in buyer goes to their home, an
                    agency user to the dashboard (or /login, via ProtectedLayout,
                    if neither session exists). */}
                <Route path="*" element={<NotFoundRedirect />} />

            </Routes>
        </BrowserRouter>
    );
}
