import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertCircle } from "lucide-react";

type Props = { children: ReactNode };
type State = { hasError: boolean };

/** Top-level safety net: catches an unexpected render crash anywhere in the
 * app and shows one plain, on-brand fallback screen instead of a blank
 * white page - the per-page loading/error/empty states (components/ui/
 * States.tsx) handle expected data-fetch failures; this is only for a bug
 * that escapes those. Logs to the console for diagnosis - never sends
 * error details anywhere, since this app has no frontend error-reporting
 * service configured. */
export default class ErrorBoundary extends Component<Props, State> {
    state: State = { hasError: false };

    static getDerivedStateFromError(): State {
        return { hasError: true };
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error("Unhandled UI error:", error, info.componentStack);
    }

    render() {
        if (!this.state.hasError) return this.props.children;

        return (
            <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-center px-6 bg-slate-50">
                <AlertCircle size={32} className="text-red-500" />
                <p className="text-base font-medium text-slate-700">Something went wrong.</p>
                <p className="text-sm text-slate-500 max-w-sm">
                    Please reload the page. If this keeps happening, contact support.
                </p>
                <button
                    onClick={() => window.location.reload()}
                    className="mt-2 px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800"
                >
                    Reload
                </button>
            </div>
        );
    }
}
