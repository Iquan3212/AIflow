import { useState } from "react";
import { useForm } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import AuthLayout from "../../components/auth/AuthLayout";
import Button from "../../components/ui/Button";
import Input, { Label, FieldError } from "../../components/ui/Input";
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
        <AuthLayout title="Welcome back" subtitle="Sign in to continue to your AI Workforce.">
            <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3.5 text-sm" role="alert">
                        {error}
                    </div>
                )}

                <div>
                    <Label htmlFor="email">Email</Label>
                    <Input
                        id="email"
                        type="email"
                        autoComplete="email"
                        invalid={!!errors.email}
                        aria-invalid={!!errors.email}
                        {...register("email", { required: "Email is required" })}
                    />
                    <FieldError>{errors.email?.message}</FieldError>
                </div>

                <div>
                    <Label htmlFor="password">Password</Label>
                    <div className="relative">
                        <Input
                            id="password"
                            type={showPassword ? "text" : "password"}
                            autoComplete="current-password"
                            className="pr-11"
                            invalid={!!errors.password}
                            aria-invalid={!!errors.password}
                            {...register("password", { required: "Password is required" })}
                        />
                        <button
                            type="button"
                            onClick={() => setShowPassword((v) => !v)}
                            aria-label={showPassword ? "Hide password" : "Show password"}
                            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                        >
                            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                    </div>
                    <FieldError>{errors.password?.message}</FieldError>
                </div>

                <Button type="submit" size="lg" loading={loading} className="w-full">
                    {loading ? "Signing in…" : "Sign In"}
                </Button>

                <p className="text-center text-sm text-slate-500">
                    Don&apos;t have an account?{" "}
                    <Link to="/register" className="text-brand-600 font-medium hover:text-brand-700">
                        Start free
                    </Link>
                </p>
            </form>
        </AuthLayout>
    );
}
