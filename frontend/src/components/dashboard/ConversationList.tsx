const conversations = [
    {
        id: 1,
        name: "John",
        message: "Asked about pricing",
        time: "2 mins ago",
        online: true,
    },
    {
        id: 2,
        name: "Sarah",
        message: "Booked appointment",
        time: "8 mins ago",
        online: false,
    },
    {
        id: 3,
        name: "Rahul",
        message: "Requested brochure",
        time: "20 mins ago",
        online: true,
    },
    {
        id: 4,
        name: "Ahmed",
        message: "Asked for quotation",
        time: "35 mins ago",
        online: true,
    },
];

export default function ConversationList() {
    return (
        <div className="bg-white rounded-3xl shadow-sm h-full">
            <div className="p-6 border-b">
                <h2 className="text-2xl font-bold">
                    Conversations
                </h2>
            </div>

            {conversations.map((chat) => (
                <div
                    key={chat.id}
                    className="p-5 border-b cursor-pointer hover:bg-slate-50"
                >
                    <div className="flex justify-between">
                        <h3 className="font-semibold">
                            {chat.name}
                        </h3>

                        <div
                            className={`w-3 h-3 rounded-full ${
                                chat.online
                                    ? "bg-green-500"
                                    : "bg-gray-300"
                            }`}
                        />
                    </div>

                    <p className="text-gray-500 text-sm mt-1">
                        {chat.message}
                    </p>

                    <p className="text-xs text-gray-400 mt-2">
                        {chat.time}
                    </p>
                </div>
            ))}
        </div>
    );
}