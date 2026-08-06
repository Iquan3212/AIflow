const pipeline = [
    ["New", 18],
    ["Qualified", 9],
    ["Negotiation", 4],
    ["Won", 6],
];

export default function LeadPipeline() {
    return (
        <div className="bg-white rounded-3xl shadow-sm p-6">

            <h2 className="text-xl font-bold mb-5">
                Lead Pipeline
            </h2>

            {pipeline.map(([stage, count]) => (

                <div
                    key={stage}
                    className="flex justify-between py-3 border-b last:border-none"
                >

                    <span>{stage}</span>

                    <span className="font-bold">
                        {count}
                    </span>

                </div>

            ))}

        </div>
    );
}