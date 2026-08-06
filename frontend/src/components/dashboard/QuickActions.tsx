import {
    Upload,
    Bot,
    Send,
    PlusCircle,
} from "lucide-react";

const actions = [
    {
        title: "Train AI",
        icon: Bot,
    },
    {
        title: "Upload Docs",
        icon: Upload,
    },
    {
        title: "Broadcast",
        icon: Send,
    },
    {
        title: "Add FAQ",
        icon: PlusCircle,
    },
];

export default function QuickActions() {
    return (
        <div className="bg-white rounded-3xl shadow-sm p-6">

            <h2 className="text-xl font-bold mb-6">
                Quick Actions
            </h2>

            <div className="grid grid-cols-2 gap-4">

                {actions.map((item) => {

                    const Icon = item.icon;

                    return (

                        <button
                            key={item.title}
                            className="rounded-2xl border p-6 hover:bg-blue-50 transition"
                        >

                            <Icon
                                className="mx-auto mb-3 text-blue-600"
                            />

                            {item.title}

                        </button>

                    );

                })}

            </div>

        </div>
    );
}