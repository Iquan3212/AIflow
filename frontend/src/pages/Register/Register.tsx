import { useState } from "react";
import { useForm } from "react-hook-form";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import AuthLayout from "../../components/auth/AuthLayout";
import { useAuth } from "../../context/AuthContext";
import api from "../../services/api";

type RegisterForm = {
    business_name: string;
    industry: string;
    owner_email: string;
    password: string;
    confirmPassword: string;
};

export default function Register() {
    const navigate = useNavigate();
    const auth = useAuth();

    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [error, setError] = useState("");

    const {
        register,
        handleSubmit,
        watch,
        formState: { errors },
    } = useForm<RegisterForm>();

    async function onSubmit(data: RegisterForm) {
        setLoading(true);
        setError("");

        try {
            const response = await api.post("/auth/signup", {
                business_name: data.business_name,
                industry: data.industry,
                owner_email: data.owner_email,
                password: data.password,
            });

            auth.login(response.data.access_token);

            localStorage.setItem(
                "business_slug",
                response.data.business_slug
            );

            navigate("/dashboard");

        } catch (err: any) {
            setError(
                err?.response?.data?.detail ||
                "Unable to create account."
            );
        } finally {
            setLoading(false);
        }
    }

    return (
        <AuthLayout
            title="Create your account"
            subtitle="Start automating your business with AIFlow."
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
                        Business Name
                    </label>

                    <input
                        {...register("business_name", {
                            required: "Business name is required",
                        })}
                        className="w-full mt-2 border rounded-xl px-4 py-3"
                    />

                    {errors.business_name && (
                        <p className="text-red-500 text-sm mt-1">
                            {errors.business_name.message}
                        </p>
                    )}

                </div>

                <div>

                    <label className="text-sm font-medium">
                        Industry
                    </label>

                    <input
                        {...register("industry", {
                            required: "Industry is required",
                        })}
                        className="w-full mt-2 border rounded-xl px-4 py-3"
                    />

                </div>

                <div>

                    <label className="text-sm font-medium">
                        Email
                    </label>

                    <input
                        type="email"
                        {...register("owner_email", {
                            required: "Email is required",
                        })}
                        className="w-full mt-2 border rounded-xl px-4 py-3"
                    />

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
                                minLength: {
                                    value: 8,
                                    message: "Minimum 8 characters",
                                },
                            })}
                            className="w-full border rounded-xl px-4 py-3 pr-12"
                        />

                        <button
                            type="button"
                            className="absolute right-4 top-3"
                            onClick={() =>
                                setShowPassword(!showPassword)
                            }
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

                <div>

                    <label className="text-sm font-medium">
                        Confirm Password
                    </label>

                    <div className="relative mt-2">

                        <input
                            type={
                                showConfirmPassword
                                    ? "text"
                                    : "password"
                            }
                            {...register("confirmPassword", {
                                validate: value =>
                                    value === watch("password") ||
                                    "Passwords do not match",
                            })}
                            className="w-full border rounded-xl px-4 py-3 pr-12"
                        />

                        <button
                            type="button"
                            className="absolute right-4 top-3"
                            onClick={() =>
                                setShowConfirmPassword(
                                    !showConfirmPassword
                                )
                            }
                        >
                            {showConfirmPassword
                                ? <EyeOff size={20}/>
                                : <Eye size={20}/>
                            }
                        </button>

                    </div>

                    {errors.confirmPassword && (
                        <p className="text-red-500 text-sm mt-1">
                            {errors.confirmPassword.message}
                        </p>
                    )}

                </div>

                <button
                    disabled={loading}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-xl py-3 font-semibold flex justify-center items-center gap-2"
                >

                    {loading
                        ? <>
                            <Loader2
                                className="animate-spin"
                                size={18}
                            />
                            Creating Account...
                        </>
                        : "Create Account"
                    }

                </button>

                <div className="text-center text-sm text-slate-500">

                    Already have an account?{" "}

                    <Link
                        to="/"
                        className="text-blue-600 hover:underline"
                    >
                        Login
                    </Link>

                </div>

            </form>

        </AuthLayout>
    );
}