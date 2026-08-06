import {
    Bell,
    Search,
} from "lucide-react";

import { useBusiness } from "../../context/BusinessContext";

export default function Navbar() {

    const {
        business,
        loading,
    } = useBusiness();

    return (

        <header className="bg-white h-20 border-b flex items-center justify-between px-8">

            <div className="relative">

                <Search
                    size={18}
                    className="absolute left-4 top-4 text-gray-400"
                />

                <input
                    placeholder="Search..."
                    className="w-80 rounded-xl border pl-11 pr-4 py-3 outline-none"
                />

            </div>

            <div className="flex items-center gap-6">

                <Bell size={22} />

                <div className="flex items-center gap-3">

                    <div className="w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center font-semibold">

                        {loading
                            ? "..."
                            : business?.name.charAt(0).toUpperCase()
                        }

                    </div>

                    <div>

                        <div className="font-semibold">

                            {loading
                                ? "Loading..."
                                : business?.name
                            }

                        </div>

                        <div className="text-sm text-gray-500">

                            {loading
                                ? ""
                                : business?.plan.toUpperCase()
                            }

                        </div>

                    </div>

                </div>

            </div>

        </header>

    );

}