import type { ReactNode } from "react";

import BuyerNav from "./BuyerNav";
import CompareBar from "../marketplace/CompareBar";
import { useBuyerAuth } from "../../context/BuyerAuthContext";

/** One shared shell for every buyer-facing screen - public marketplace
 * pages (Discover, project/property detail) and buyer-authenticated
 * pages (Home, Saved, Compare, My Activity, Assistant, Profile) alike.
 * Replaces the old separate MarketplaceHeader/BuyerShell: same auth
 * boundary, one nav component that adapts to it, so a signed-in buyer
 * never loses their navigation moving between "browsing" and "my
 * account" pages. `bare` skips the max-width content padding for pages
 * that want their own full-bleed layout (e.g. Discover's own two-column
 * grid) while still getting the nav and bottom-tab spacing. The floating
 * compare bar lives here (not scattered across every page that offers a
 * compare toggle) so a selection made anywhere is visible everywhere -
 * `hideCompareBar` opts out only on the Compare page itself, which
 * already shows the same selection as its own full page. */
export default function BuyerLayout({
    children,
    bare = false,
    hideCompareBar = false,
}: {
    children: ReactNode;
    bare?: boolean;
    hideCompareBar?: boolean;
}) {
    const { isAuthenticated } = useBuyerAuth();

    return (
        <div className="min-h-screen bg-stone-50">
            <BuyerNav />
            <div className={isAuthenticated ? "lg:pb-0 pb-16" : ""}>
                {bare ? children : (
                    <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">{children}</main>
                )}
            </div>
            {!hideCompareBar && <CompareBar />}
        </div>
    );
}
