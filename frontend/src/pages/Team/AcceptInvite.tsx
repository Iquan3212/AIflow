import { useState } from "react";
import { useForm } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import AuthLayout from "../../components/auth/AuthLayout";
import Button from "../../components/ui/Button";
import Input, { Label, FieldError } from "../../components/ui/Input";
import { useAuth } from "../../context/AuthContext";
import { acceptInvite } from "../../services/team";
import { getErrorMessage } from "../../services/api";

type AcceptForm = {
    password: string;
    confirmPassword: string;
};

/** Public - the invitee has no account yet, so this can't live behind
 * ProtectedLayout or PublicOnlyLayout (which only makes sense once a
 * session either does or doesn't already exist for this exact purpose). */
export default function AcceptInvite() {
    const navigate = useNavigate();
    const auth = useAuth();
    const [searchParams] = useSearchParams();
    const token = searchParams.get("token") ?? "";

    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");

    const {
        register,
        handleSubmit,
        watch,
        formState: { errors },
    } = useForm<AcceptForm>();

    async function onSubmit(data: AcceptForm) {
        if (!token) {
            setError("This invite link is missing its token.");
            return;
        }
        setLoading(true);
        setError("");
        try {
            const tokens = await acceptInvite(token, data.password);
            auth.login(tokens);
            navigate("/dashboard");
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }

    if (!token) {
        return (
            <AuthLayout title="Invalid invite link" subtitle="This link is missing its invite token.">
                <p className="text-center text-sm text-slate-500">
                    Ask whoever invited you to send the invite again, or{" "}
                    <Link to="/login" className="text-brand-600 font-medium hover:text-brand-700">sign in</Link> if you already have an account.
                </p>
            </AuthLayout>
        );
    }

    return (
        <AuthLayout title="Join your team on AIFlow" subtitle="Set a password to activate your account.">
            <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3.5 text-sm" role="alert">
                        {error}
                    </div>
                )}

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
                                minLength: { value: 8, message: "Must be at least 8 characters" },
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
                            required: "Please confirm your password",
                            validate: (value) => value === watch("password") || "Passwords don't match",
                        })}
                    />
                    <FieldError>{errors.confirmPassword?.message}</FieldError>
                </div>

                <Button type="submit" size="lg" loading={loading} className="w-full">
                    {loading ? "Activating…" : "Activate account"}
                </Button>

                <p className="text-center text-sm text-slate-500">
                    Already have an account?{" "}
                    <Link to="/login" className="text-brand-600 font-medium hover:text-brand-700">Sign in</Link>
                </p>
            </form>
        </AuthLayout>
    );
}
