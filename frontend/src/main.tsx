import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";

import ErrorBoundary from "./components/ErrorBoundary";
import { AuthProvider } from "./context/AuthContext";
import { AgencyProvider } from "./context/AgencyContext";
import { BuyerAuthProvider } from "./context/BuyerAuthContext";
import { CompareProvider } from "./context/CompareContext";

import "./index.css";

ReactDOM.createRoot(
    document.getElementById("root")!
).render(

    <React.StrictMode>

        <ErrorBoundary>

            <AuthProvider>

                <AgencyProvider>

                    <BuyerAuthProvider>

                        <CompareProvider>

                            <App />

                        </CompareProvider>

                    </BuyerAuthProvider>

                </AgencyProvider>

            </AuthProvider>

        </ErrorBoundary>

    </React.StrictMode>

);