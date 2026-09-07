import { User } from "lucide-react";
import type { ReactNode } from "react";
import type { Conversation } from "../../types/conversation";
import { EmptyState } from "../ui/States";

type Props = {
    conversation: Conversation | null;
};

function Field({ label, value }: { label: string; value: ReactNode }) {
    return (
        <div>
            <p className="text-slate-500 text-xs uppercase tracking-wide font-medium">{label}</p>
            <p className="font-medium text-slate-900 mt-1.5">{value}</p>
        </div>
    );
}

export default function CustomerInfo({ conversation }: Props) {
    return (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-soft h-full p-5 overflow-y-auto thin-scrollbar">
            <h2 className="font-display font-semibold text-slate-900 mb-5">Customer Details</h2>

            {!conversation ? (
                <EmptyState icon={<User size={24} />} title="No customer selected" />
            ) : (
                <div className="space-y-5">
                    <Field
                        label="Name"
                        value={
                            conversation.customer_name ?? <span className="font-normal text-slate-400">Not provided yet</span>
                        }
                    />
                    <Field label="Phone" value={conversation.phone || "Not available"} />
                    <Field label="Total messages" value={conversation.total_messages} />
                </div>
            )}
        </div>
    );
}
