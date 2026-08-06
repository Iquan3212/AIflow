import type {
    Message,
} from "../../types/conversation";

type Props = {
    message: Message;
};

export default function MessageBubble({
    message,
}: Props) {

    const isUser =
        message.sender === "user";

    return (

        <div
            className={`flex mb-4

            ${
                isUser
                    ? "justify-end"
                    : "justify-start"
            }`}
        >

            <div
                className={`rounded-2xl px-5 py-3 max-w-md

                ${
                    isUser
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100"
                }`}
            >

                {message.text}

            </div>

        </div>

    );

}