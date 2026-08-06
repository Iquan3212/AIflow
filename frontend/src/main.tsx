import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";

import { AuthProvider } from "./context/AuthContext";
import { BusinessProvider } from "./context/BusinessContext";

import "./index.css";

ReactDOM.createRoot(
    document.getElementById("root")!
).render(

    <React.StrictMode>

        <AuthProvider>

            <BusinessProvider>

                <App />

            </BusinessProvider>

        </AuthProvider>

    </React.StrictMode>

);