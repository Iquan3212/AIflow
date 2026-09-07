import { useState } from "react";
import { useForm } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import AuthLayout from "../../components/auth/AuthLayout";
import Button from "../../components/ui/Button";
import Input, { Label, FieldError } from "../../components/ui/Input";
import { useAuth } from "../../context/AuthContext";
import { register as registerRequest } from "../../services/auth";
import { getErrorMessage } from "../../services/api";

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
            const tokens = await registerRequest({
                business_name: data.business_name,
                industry: data.industry,
                owner_email: data.owner_email,
                password: data.password,
            });

            auth.login(tokens);
            navigate("/dashboard");
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }

    return (
        <AuthLayout title="Start free" subtitle="Set up your business and meet your AI Workforce.">
            <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3.5 text-sm" role="alert">
                        {error}
                    </div>
                )}

                <div>
                    <Label htmlFor="business_name">Business name</Label>
                    <Input
                        id="business_name"
                        autoComplete="organization"
                        invalid={!!errors.business_name}
                        aria-invalid={!!errors.business_name}
                        {...register("business_name", { required: "Business name is required" })}
                    />
                    <FieldError>{errors.business_name?.message}</FieldError>
                </div>

                <div>
                    <Label htmlFor="industry">Industry</Label>
                    <Input
                        id="industry"
                        placeholder="e.g. Restaurant, Salon, Retail"
                        invalid={!!errors.industry}
                        aria-invalid={!!errors.industry}
                        {...register("industry", { required: "Industry is required" })}
                    />
                    <FieldError>{errors.industry?.message}</FieldError>
                </div>

                <div>
                    <Label htmlFor="owner_email">Email</Label>
                    <Input
                        id="owner_email"
                        type="email"
                        autoComplete="email"
                        invalid={!!errors.owner_email}
                        aria-invalid={!!errors.owner_email}
                        {...register("owner_email", { required: "Email is required" })}
                    />
                    <FieldError>{errors.owner_email?.message}</FieldError>
                </div>

                <div>
                    <Label htmlFor="password">Password</Label>
                    <div className="relative">
                        <Input
                            id="password"
                            type={showPassword ? "text" : "password"}
                            autoComplete="new-password"
                            className="pr-11"
                            invalid={!!errors.password}
                            aria-invalid={!!errors.password}
                            {...register("password", {
                                required: "Password is required",
                                minLength: { value: 8, message: "Minimum 8 characters" },
                            })}
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

                <div>
                    <Label htmlFor="confirmPassword">Confirm password</Label>
                    <div className="relative">
                        <Input
                            id="confirmPassword"
                            type={showConfirmPassword ? "text" : "password"}
                            autoComplete="new-password"
                            className="pr-11"
                            invalid={!!errors.confirmPassword}
                            aria-invalid={!!errors.confirmPassword}
                            {...register("confirmPassword", {
                                validate: (value) => value === watch("password") || "Passwords do not match",
                            })}
                        />
                        <button
                            type="button"
                            onClick={() => setShowConfirmPassword((v) => !v)}
                            aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                        >
                            {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                        </button>
                    </div>
                    <FieldError>{errors.confirmPassword?.message}</FieldError>
                </div>

                <Button type="submit" size="lg" loading={loading} className="w-full">
                    {loading ? "Creating account…" : "Create account"}
                </Button>

                <p className="text-center text-sm text-slate-500">
                    Already have an account?{" "}
                    <Link to="/login" className="text-brand-600 font-medium hover:text-brand-700">
                        Sign in
                    </Link>
                </p>
            </form>
        </AuthLayout>
    );
}
