import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";

export default function ConversationWindow() {
    return (
        <div className="bg-white rounded-3xl shadow-sm flex flex-col h-full">

            <div className="p-6 border-b">
                <h2 className="text-xl font-bold">
                    John
                </h2>

                <p className="text-green-500 text-sm">
                    Online
                </p>
            </div>

            <div className="flex-1 p-6 overflow-y-auto bg-slate-50">

                <MessageBubble
                    sender="user"
                    text="Hi, I need a quotation."
                    time="10:10 AM"
                />

                <MessageBubble
                    sender="ai"
                    text="Sure 👋 Which service are you interested in?"
                    time="10:11 AM"
                />

                <MessageBubble
                    sender="user"
                    text="Car detailing."
                    time="10:12 AM"
                />

            </div>

            <div className="p-6 border-t">

                <ChatInput />

            </div>

        </div>
    );
}