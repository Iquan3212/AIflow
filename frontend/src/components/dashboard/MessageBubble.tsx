type Props = {
    sender: "user" | "ai";
    text: string;
    time: string;
};

export default function MessageBubble({
    sender,
    text,
    time,
}: Props) {
    const isAI = sender === "ai";

    return (
        <div
            className={`flex ${
                isAI ? "justify-start" : "justify-end"
            } mb-5`}
        >
            <div
                className={`max-w-md rounded-2xl px-5 py-3 shadow-sm ${
                    isAI
                        ? "bg-white text-gray-800"
                        : "bg-blue-600 text-white"
                }`}
            >
                <p>{text}</p>

                <div
                    className={`text-xs mt-2 ${
                        isAI
                            ? "text-gray-400"
                            : "text-blue-100"
                    }`}
                >
                    {time}
                </div>
            </div>
        </div>
    );
}