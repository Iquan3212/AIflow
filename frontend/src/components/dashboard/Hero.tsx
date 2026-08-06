import { Bot } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useBusiness } from "../../context/BusinessContext";

export default function Hero() {

    const navigate = useNavigate();
    const { business } = useBusiness();

    return (

        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-3xl text-white p-10 shadow-lg">

            <div className="flex justify-between items-center">

                <div>

                    <p className="text-blue-100 text-lg">
                        Good Afternoon 👋
                    </p>

                    <h1 className="text-5xl font-bold mt-2">
                        Welcome back, {business?.name || "there"}
                    </h1>

                    <p className="mt-5 text-blue-100 text-lg max-w-2xl">
                        Your AI employee has been working while you were away.
                        Here's today's performance summary.
                    </p>

                    <div className="flex gap-5 mt-8">

                        <button
                            onClick={() => navigate("/manager")}
                            className="bg-white text-blue-700 font-semibold px-6 py-3 rounded-xl hover:bg-gray-100 transition"
                        >
                            Open AI Assistant
                        </button>

                        <button
                            onClick={() => navigate("/conversations")}
                            className="border border-white px-6 py-3 rounded-xl hover:bg-white hover:text-blue-700 transition"
                        >
                            View Conversations
                        </button>

                    </div>

                </div>

                <div className="hidden lg:flex">

                    <div className="bg-white/10 backdrop-blur rounded-3xl p-8">

                        <Bot size={90} />

                    </div>

                </div>

            </div>

        </div>

    );

}
