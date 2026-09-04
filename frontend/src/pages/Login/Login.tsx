import { useState } from "react";
import { useForm } from "react-hook-form";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import AuthLayout from "../../components/auth/AuthLayout";
import { useAuth } from "../../context/AuthContext";
import { login as loginRequest } from "../../services/auth";
import { getErrorMessage } from "../../services/api";

type LoginForm = {
    email: string;
    password: string;
};

export default function Login() {
    const navigate = useNavigate();
    const auth = useAuth();

    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm<LoginForm>();

    async function onSubmit(data: LoginForm) {
        setLoading(true);
        setError("");

        try {
            const tokens = await loginRequest(data);
            auth.login(tokens);
            navigate("/dashboard");
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }

    return (
        <AuthLayout
            title="Welcome Back"
            subtitle="Login to continue using AIFlow."
        >

            <form
                onSubmit={handleSubmit(onSubmit)}
                className="space-y-5"
            >

                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl p-3 text-sm">
                        {error}
                    </div>
                )}

                <div>

                    <label className="text-sm font-medium">
                        Email
                    </label>

                    <input
                        type="email"
                        {...register("email", {
                            required: "Email is required",
                        })}
                        className="w-full mt-2 border rounded-xl px-4 py-3 outline-none focus:border-blue-600"
                    />

                    {errors.email && (
                        <p className="text-red-500 text-sm mt-1">
                            {errors.email.message}
                        </p>
                    )}

                </div>

                <div>

                    <label className="text-sm font-medium">
                        Password
                    </label>

                    <div className="relative mt-2">

                        <input
                            type={
                                showPassword
                                    ? "text"
                                    : "password"
                            }
                            {...register("password", {
                                required: "Password is required",
                            })}
                            className="w-full border rounded-xl px-4 py-3 pr-12 outline-none focus:border-blue-600"
                        />

                        <button
                            type="button"
                            onClick={() =>
                                setShowPassword(!showPassword)
                            }
                            className="absolute right-4 top-3 text-slate-500"
                        >
                            {showPassword
                                ? <EyeOff size={20}/>
                                : <Eye size={20}/>
                            }
                        </button>

                    </div>

                    {errors.password && (
                        <p className="text-red-500 text-sm mt-1">
                            {errors.password.message}
                        </p>
                    )}

                </div>

                <button
                    disabled={loading}
                    className="
                        w-full
                        bg-blue-600
                        hover:bg-blue-700
                        text-white
                        py-3
                        rounded-xl
                        font-semibold
                        transition
                        flex
                        justify-center
                        items-center
                        gap-2
                    "
                >

                    {loading
                        ? <>
                            <Loader2
                                className="animate-spin"
                                size={18}
                            />
                            Logging in...
                        </>
                        : "Login"
                    }

                </button>

                <div className="text-center text-sm text-slate-500">

                    Don't have an account?{" "}

                    <Link
                        to="/register"
                        className="text-blue-600 hover:underline"
                    >
                        Create Account
                    </Link>

                </div>

            </form>

        </AuthLayout>
    );
}