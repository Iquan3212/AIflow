const logs = [
    "AI answered customer",
    "Lead captured",
    "Appointment booked",
    "Invoice generated",
];

export default function ActivityFeed() {
    return (
        <div className="bg-white rounded-3xl shadow-sm p-6">

            <h2 className="text-xl font-bold mb-5">
                Activity Feed
            </h2>

            {logs.map(log => (

                <div
                    key={log}
                    className="py-4 border-b last:border-none"
                >

                    <div className="font-medium">
                        {log}
                    </div>

                    <div className="text-gray-500 text-sm">
                        Just now
                    </div>

                </div>

            ))}

        </div>
    );
}