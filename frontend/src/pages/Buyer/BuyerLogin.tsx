import { useState } from "react";
import { useForm } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import AuthLayout from "../../components/auth/AuthLayout";
import Button from "../../components/ui/Button";
import Input, { Label, FieldError } from "../../components/ui/Input";
import { useBuyerAuth } from "../../context/BuyerAuthContext";
import { buyerLogin } from "../../services/buyerAuth";
import { getErrorMessage } from "../../services/api";

type LoginForm = {
    email: string;
    password: string;
};

const BUYER_STRIP = ["Discover", "Match", "Site Visit", "Save", "Compare"];

export default function BuyerLogin() {
    const navigate = useNavigate();
    const buyerAuth = useBuyerAuth();

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
            const tokens = await buyerLogin(data);
            buyerAuth.login(tokens);
            navigate("/buyer/home");
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }

    return (
        <AuthLayout title="Welcome back" subtitle="Sign in to pick up where you left off." strip={BUYER_STRIP}>
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

                <Button type="submit" size="lg" variant="flare" loading={loading} className="w-full">
                    {loading ? "Signing in…" : "Sign In"}
                </Button>

                <p className="text-center text-sm text-slate-500">
                    New to AIFlow?{" "}
                    <Link to="/buyer/register" className="text-brand-600 font-medium hover:text-brand-700">
                        Create a buyer account
                    </Link>
                </p>
                <p className="text-center text-xs text-slate-400">
                    Run an agency instead?{" "}
                    <Link to="/login" className="text-slate-600 font-medium hover:text-ink-950">
                        Agency sign in
                    </Link>
                </p>
            </form>
        </AuthLayout>
    );
}
