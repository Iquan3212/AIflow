import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";

import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider } from "./context/AuthContext";
import { BusinessProvider } from "./context/BusinessContext";

import "./index.css";

ReactDOM.createRoot(
    document.getElementById("root")!
).render(

    <React.StrictMode>

        <ErrorBoundary>

            <AuthProvider>

                <BusinessProvider>

                    <App />

                </BusinessProvider>

            </AuthProvider>

        </ErrorBoundary>

    </React.StrictMode>

);