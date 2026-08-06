import Sidebar from "./Sidebar";
import Navbar from "./Navbar";

type Props = {
    children: React.ReactNode;
};

export default function Layout({ children }: Props) {
    return (
        <div className="bg-slate-100 min-h-screen">

            {/* Fixed Sidebar */}
            <Sidebar />

            {/* Right Side */}
            <div className="ml-64 flex flex-col min-h-screen">

                <Navbar />

                <main className="flex-1 p-8 overflow-auto">

                    {children}

                </main>

            </div>

        </div>
    );
}