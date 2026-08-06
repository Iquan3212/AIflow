import {
    LineChart,
    Line,
    ResponsiveContainer,
    XAxis,
    YAxis,
    Tooltip,
} from "recharts";

const data = [
    { day: "Mon", chats: 20 },
    { day: "Tue", chats: 35 },
    { day: "Wed", chats: 29 },
    { day: "Thu", chats: 41 },
    { day: "Fri", chats: 50 },
    { day: "Sat", chats: 43 },
];

export default function AnalyticsChart() {
    return (
        <div className="bg-white rounded-3xl shadow-sm p-6">

            <h2 className="text-xl font-bold mb-6">
                Weekly Conversations
            </h2>

            <div style={{ width: "100%", height: 300 }}>

                <ResponsiveContainer>

                    <LineChart data={data}>

                        <XAxis dataKey="day" />

                        <YAxis />

                        <Tooltip />

                        <Line
                            dataKey="chats"
                            stroke="#2563eb"
                            strokeWidth={3}
                        />

                    </LineChart>

                </ResponsiveContainer>

            </div>

        </div>
    );
}