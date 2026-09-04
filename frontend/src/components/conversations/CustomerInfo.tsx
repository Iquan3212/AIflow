import type { Conversation } from "../../types/conversation";

type Props = {
    conversation: Conversation | null;
};

export default function CustomerInfo({
    conversation,
}: Props) {

    return (

        <div className="bg-white rounded-2xl shadow h-full p-6">

            <h2 className="text-xl font-bold mb-6">

                Customer Details

            </h2>

            {

                !conversation ? (

                    <div className="text-gray-400 text-sm">

                        No customer selected.

                    </div>

                ) : (

                    <>

                        <div className="mb-6">

                            <p className="text-gray-500 text-sm">

                                Name

                            </p>

                            <p className="font-semibold mt-1">

                                {conversation.customer_name ?? (
                                    <span className="font-normal text-gray-400">
                                        Not provided yet
                                    </span>
                                )}

                            </p>

                        </div>

                        <div className="mb-6">

                            <p className="text-gray-500 text-sm">

                                Phone

                            </p>

                            <p className="font-semibold mt-1">

                                {conversation.phone || "Not available"}

                            </p>

                        </div>

                        <div>

                            <p className="text-gray-500 text-sm">

                                Total Messages

                            </p>

                            <p className="font-semibold mt-1">

                                {conversation.total_messages}

                            </p>

                        </div>

                    </>

                )

            }

        </div>

    );

}
