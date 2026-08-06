import type { ReactNode } from "react";
import { Bot } from "lucide-react";

interface Props {
    title: string;
    subtitle: string;
    children: ReactNode;
}

export default function AuthLayout({
    title,
    subtitle,
    children,
}: Props) {
    return (
        <div className="min-h-screen bg-slate-950 flex">

            {/* LEFT */}

            <div className="hidden lg:flex w-1/2 bg-gradient-to-br from-blue-700 via-indigo-700 to-slate-900 text-white p-16 flex-col justify-between">

                <div>

                    <div className="flex items-center gap-3">

                        <div className="bg-white/20 p-3 rounded-2xl">
                            <Bot size={34}/>
                        </div>

                        <h1 className="text-4xl font-bold">
                            AIFlow
                        </h1>

                    </div>

                    <p className="text-xl mt-10 leading-10 text-slate-200">

                        Your AI employee that works
                        24 hours a day.

                        <br />

                        Automate conversations,
                        capture leads,
                        schedule appointments
                        and grow your business.

                    </p>

                </div>

                <div className="text-slate-300 text-sm">

                    © 2026 AIFlow Technologies

                </div>

            </div>

            {/* RIGHT */}

            <div className="flex-1 flex justify-center items-center bg-slate-100">

                <div className="bg-white rounded-3xl shadow-xl w-full max-w-md p-10">

                    <h2 className="text-4xl font-bold text-slate-900">
                        {title}
                    </h2>

                    <p className="text-slate-500 mt-3 mb-10">
                        {subtitle}
                    </p>

                    {children}

                </div>

            </div>

        </div>
    );
}