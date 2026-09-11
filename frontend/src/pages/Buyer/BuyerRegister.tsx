import { useState } from "react";
import { useForm } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import AuthLayout from "../../components/auth/AuthLayout";
import Button from "../../components/ui/Button";
import Input, { Label, FieldError } from "../../components/ui/Input";
import { useBuyerAuth } from "../../context/BuyerAuthContext";
import { buyerSignup } from "../../services/buyerAuth";
import { getErrorMessage } from "../../services/api";

type RegisterForm = {
    name: string;
    email: string;
    phone: string;
    password: string;
    confirmPassword: string;
};

const BUYER_STRIP = ["Discover", "Match", "Site Visit", "Save", "Compare"];

export default function BuyerRegister() {
    const navigate = useNavigate();
    const buyerAuth = useBuyerAuth();

    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
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
            const tokens = await buyerSignup({
                name: data.name,
                email: data.email,
                phone: data.phone || undefined,
                password: data.password,
            });
            buyerAuth.login(tokens);
            navigate("/buyer/home");
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }

    return (
        <AuthLayout title="Create your buyer account" subtitle="Free — save properties and pick up conversations across visits." strip={BUYER_STRIP}>
            <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3.5 text-sm" role="alert">
                        {error}
                    </div>
                )}

                <div>
                    <Label htmlFor="name">Full name</Label>
                    <Input
                        id="name"
                        autoComplete="name"
                        invalid={!!errors.name}
                        aria-invalid={!!errors.name}
                        {...register("name", { required: "Name is required" })}
                    />
                    <FieldError>{errors.name?.message}</FieldError>
                </div>

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
                    <Label htmlFor="phone">Phone (optional)</Label>
                    <Input id="phone" type="tel" autoComplete="tel" {...register("phone")} />
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
                    <Input
                        id="confirmPassword"
                        type={showPassword ? "text" : "password"}
                        autoComplete="new-password"
                        invalid={!!errors.confirmPassword}
                        aria-invalid={!!errors.confirmPassword}
                        {...register("confirmPassword", {
                            validate: (value) => value === watch("password") || "Passwords do not match",
                        })}
                    />
                    <FieldError>{errors.confirmPassword?.message}</FieldError>
                </div>

                <Button type="submit" size="lg" variant="flare" loading={loading} className="w-full">
                    {loading ? "Creating account…" : "Create account"}
                </Button>

                <p className="text-center text-sm text-slate-500">
                    Already have an account?{" "}
                    <Link to="/buyer/login" className="text-brand-600 font-medium hover:text-brand-700">
                        Sign in
                    </Link>
                </p>
            </form>
        </AuthLayout>
    );
}
