import {
    MessageCircle,
    Users,
    Calendar,
    IndianRupee,
    ArrowUpRight,
} from "lucide-react";

type DashboardStats = {
    today_chats: number;
    new_leads: number;
    appointments: number;
    revenue: number;
};

type Props = {
    stats: DashboardStats;
};

export default function DashboardCards({ stats }: Props) {

    const cards = [
        {
            title: "Today's Chats",
            value: stats.today_chats,
            growth: "+18%",
            icon: MessageCircle,
            color: "bg-blue-600",
        },
        {
            title: "New Leads",
            value: stats.new_leads,
            growth: "+12%",
            icon: Users,
            color: "bg-purple-600",
        },
        {
            title: "Appointments",
            value: stats.appointments,
            growth: "+9%",
            icon: Calendar,
            color: "bg-orange-500",
        },
        {
            title: "Revenue",
            value: `₹${stats.revenue.toLocaleString()}`,
            growth: "+27%",
            icon: IndianRupee,
            color: "bg-green-600",
        },
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">

            {cards.map((card) => {

                const Icon = card.icon;

                return (

                    <div
                        key={card.title}
                        className="
                        group
                        bg-white
                        rounded-3xl
                        p-6
                        border
                        border-slate-200
                        shadow-sm
                        hover:shadow-xl
                        hover:-translate-y-1
                        transition-all
                        duration-300
                    "
                    >

                        <div className="flex justify-between">

                            <div>

                                <p className="text-slate-500 text-sm">
                                    {card.title}
                                </p>

                                <h2 className="text-4xl font-bold mt-3">
                                    {card.value}
                                </h2>

                                <div className="flex items-center gap-1 mt-4 text-green-600 font-semibold">

                                    <ArrowUpRight size={16} />

                                    {card.growth}

                                    <span className="text-slate-400 font-normal ml-1">
                                        this month
                                    </span>

                                </div>

                            </div>

                            <div
                                className={`
                                    ${card.color}
                                    w-16
                                    h-16
                                    rounded-2xl
                                    flex
                                    items-center
                                    justify-center
                                    text-white
                                    group-hover:scale-110
                                    transition
                                `}
                            >
                                <Icon size={30} />
                            </div>

                        </div>

                    </div>

                );

            })}

        </div>
    );
}