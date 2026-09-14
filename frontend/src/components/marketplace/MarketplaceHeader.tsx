import { Link, useNavigate } from "react-router-dom";
import { LogOut, User } from "lucide-react";

import Logo from "../brand/Logo";
import Button from "../ui/Button";
import { useBuyerAuth } from "../../context/BuyerAuthContext";

/** Shared across Discover, project detail, and property detail - one
 * consistent marketplace shell so a buyer never loses their bearings
 * moving between search and a listing. */
export default function MarketplaceHeader() {
    const { isAuthenticated, logout } = useBuyerAuth();
    const navigate = useNavigate();

    async function handleLogout() {
        await logout();
        navigate("/discover");
    }

    return (
        <header className="border-b border-slate-200/70 bg-white/80 backdrop-blur-xl sticky top-0 z-20">
            <div className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between gap-4">
                <Link to="/discover" aria-label="AIFlow marketplace home" className="shrink-0">
                    <Logo size="sm" />
                </Link>
                <div className="flex items-center gap-2 shrink-0">
                    {isAuthenticated ? (
                        <>
                            <Link
                                to="/buyer/home"
                                className="flex items-center gap-1.5 text-sm font-semibold text-slate-700 hover:text-ink-950 px-3.5 py-2"
                            >
                                <User size={15} /> Account
                            </Link>
                            <Button size="sm" variant="ghost" onClick={handleLogout}>
                                <LogOut size={14} /> Log out
                            </Button>
                        </>
                    ) : (
                        <>
                            <Link to="/buyer/login" className="text-sm font-semibold text-slate-700 hover:text-ink-950 px-3.5 py-2">
                                Sign in
                            </Link>
                            <Link to="/buyer/register">
                                <Button size="sm" variant="flare">Create account</Button>
                            </Link>
                        </>
                    )}
                </div>
            </div>
        </header>
    );
}
