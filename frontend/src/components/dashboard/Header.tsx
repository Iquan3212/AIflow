import { useEffect, useState } from "react";

import { getCurrentBusiness } from "../../services/business";

export default function Header() {

    const [businessName, setBusinessName] = useState("Loading...");

    useEffect(() => {

        async function loadBusiness() {

            try {

                const business = await getCurrentBusiness();

                setBusinessName(business.name);

            } catch (error) {

                console.error(error);

            }

        }

        loadBusiness();

    }, []);

    return (

        <div
            style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 30,
            }}
        >

            <div>

                <h1>Dashboard</h1>

                <p>
                    Welcome back 👋
                </p>

            </div>

            <div>

                <h2>{businessName}</h2>

            </div>

        </div>

    );

}