const chats = [
    {
        name: "John",
        message: "Asked for pricing",
        time: "2 mins",
    },
    {
        name: "Sarah",
        message: "Booked appointment",
        time: "8 mins",
    },
    {
        name: "Rahul",
        message: "Requested brochure",
        time: "13 mins",
    },
];

export default function RecentConversations() {
    return (
        <div className="bg-white rounded-3xl shadow-sm p-6">

            <h2 className="text-xl font-bold mb-5">
                Recent Conversations
            </h2>

            {chats.map(chat => (

                <div
                    key={chat.name}
                    className="border-b last:border-none py-4"
                >

                    <div className="font-semibold">
                        {chat.name}
                    </div>

                    <div className="text-gray-500 text-sm">
                        {chat.message}
                    </div>

                    <div className="text-xs mt-2 text-blue-500">
                        {chat.time} ago
                    </div>

                </div>

            ))}

        </div>
    );
}