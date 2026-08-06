import {
    Activity,
    Bot,
    Clock3,
    CheckCircle,
} from "lucide-react";

type Props = {
    model?: string;
    responseTime?: number;
    accuracy?: number;
};

export default function AIHealth({ model, responseTime, accuracy }: Props) {

    const stats = [
        {
            title: "Status",
            value: "Online",
            icon: CheckCircle,
            color: "text-green-500",
        },
        {
            title: "Model",
            value: model || "Configured model",
            icon: Bot,
            color: "text-blue-600",
        },
        {
            title: "Response",
            value: responseTime ? `${responseTime} sec` : "—",
            icon: Clock3,
            color: "text-orange-500",
        },
        {
            title: "Accuracy",
            value: accuracy ? `${accuracy}%` : "—",
            icon: Activity,
            color: "text-purple-600",
        },
    ];

    return (

        <div className="grid grid-cols-4 gap-6">

            {stats.map((item) => {

                const Icon = item.icon;

                return (

                    <div
                        key={item.title}
                        className="bg-white rounded-3xl p-6 shadow-sm"
                    >

                        <div className="flex justify-between">

                            <div>

                                <div className="text-gray-500">

                                    {item.title}

                                </div>

                                <div className="text-3xl font-bold mt-3">

                                    {item.value}

                                </div>

                            </div>

                            <Icon
                                className={item.color}
                                size={34}
                            />

                        </div>

                    </div>

                );

            })}

        </div>

    );
}
