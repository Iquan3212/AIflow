import {
    LayoutDashboard,
    Users,
    MessageSquare,
    Settings,
    BarChart3,
    CalendarClock,
    Bot
} from "lucide-react";

import { NavLink } from "react-router-dom";

import "../../styles/sidebar.css";

export default function Sidebar(){

    return(

        <aside className="sidebar">

            <div className="logo">
                AIFlow
            </div>

            <nav>

                <NavLink to="/dashboard">
                    <LayoutDashboard size={20}/>
                    Dashboard
                </NavLink>

                <NavLink to="/leads">
                    <Users size={20}/>
                    Leads
                </NavLink>

                <NavLink to="/conversations">
                    <MessageSquare size={20}/>
                    Conversations
                </NavLink>

                <NavLink to="/appointments">
                    <CalendarClock size={20}/>
                    Appointments
                </NavLink>

                <NavLink to="/manager">
                    <Bot size={20}/>
                    AI Employee
                </NavLink>

                <NavLink to="/chatbot">
                    <Bot size={20}/>
                    Chatbot
                </NavLink>

                <NavLink to="/analytics">
                    <BarChart3 size={20}/>
                    Analytics
                </NavLink>

                <NavLink to="/settings">
                    <Settings size={20}/>
                    Settings
                </NavLink>

            </nav>

        </aside>

    )

}
