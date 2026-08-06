import {
    Search,
    Download,
    Plus,
    Filter,
} from "lucide-react";

type Props = {
    search: string;
    setSearch: (value: string) => void;
};

export default function LeadsToolbar({
    search,
    setSearch,
}: Props) {

    return (

        <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-5 mb-8">

            <div className="flex justify-between items-center gap-6">

                <div className="relative flex-1">

                    <Search
                        size={18}
                        className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
                    />

                    <input
                        value={search}
                        onChange={(e) =>
                            setSearch(e.target.value)
                        }
                        placeholder="Search leads by name, phone or service..."
                        className="
                            w-full
                            rounded-xl
                            border
                            border-slate-200
                            py-3
                            pl-11
                            pr-4
                            outline-none
                            focus:border-blue-500
                            transition
                        "
                    />

                </div>

                <button
                    className="
                        bg-blue-600
                        hover:bg-blue-700
                        text-white
                        px-5
                        py-3
                        rounded-xl
                        flex
                        items-center
                        gap-2
                        transition
                    "
                >
                    <Plus size={18}/>
                    Add Lead
                </button>

            </div>

            <div className="flex justify-between mt-5">

                <div className="flex gap-3">

                    <button className="border rounded-xl px-4 py-2 flex items-center gap-2 hover:bg-slate-50">
                        <Filter size={16}/>
                        Status
                    </button>

                    <button className="border rounded-xl px-4 py-2 hover:bg-slate-50">
                        Last 30 Days
                    </button>

                </div>

                <button className="border rounded-xl px-4 py-2 flex items-center gap-2 hover:bg-slate-50">
                    <Download size={16}/>
                    Export
                </button>

            </div>

        </div>

    );

}