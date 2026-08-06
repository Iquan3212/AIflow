import { BrowserRouter, Routes, Route } from "react-router-dom";

import Login from "./pages/Login/Login";
import Register from "./pages/Register/Register";
import Dashboard from "./pages/Dashboard/Dashboard";
import Conversations from "./pages/Conversations/Conversations";
import Leads from "./pages/Leads/Leads";
import Appointments from "./pages/Appointments/Appointments";

import ProtectedLayout from "./layouts/ProtectedLayout";
import Manager from "./pages/Manager/Manager";


export default function App() {
    return (
        <BrowserRouter>
            <Routes>

                {/* Public Route */}
                <Route
                    path="/"
                    element={<Login />}
                />
                <Route
                     path="/register"
                    element={<Register />}
                />

                {/* Protected Routes */}
                <Route element={<ProtectedLayout />}>

                    <Route
                        path="/dashboard"
                        element={<Dashboard />}
                    />

                    <Route
                        path="/conversations"
                        element={<Conversations />}
                    />

                    <Route
                        path="/leads"
                        element={<Leads />}
                    />

                    <Route
                        path="/appointments"
                        element={<Appointments />}
                    />
                   <Route path="/manager" element={<Manager />} />

                </Route>

            </Routes>
        </BrowserRouter>
    );
}