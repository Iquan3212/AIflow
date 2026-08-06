import { Bot, CheckCircle } from "lucide-react";

export default function AIStatus() {
    return (
        <div className="bg-white rounded-3xl shadow-sm p-6 flex justify-between items-center">

            <div>

                <h2 className="text-xl font-bold">
                    AI Employee
                </h2>

                <p className="text-gray-500 mt-2">
                    Your assistant is online and answering customers.
                </p>

                <div className="flex items-center gap-2 mt-4">

                    <CheckCircle
                        size={18}
                        className="text-green-500"
                    />

                    <span className="text-green-600 font-medium">
                        Online
                    </span>

                </div>

            </div>

            <div className="w-20 h-20 rounded-3xl bg-blue-600 text-white flex items-center justify-center">

                <Bot size={42} />

            </div>

        </div>
    );
}