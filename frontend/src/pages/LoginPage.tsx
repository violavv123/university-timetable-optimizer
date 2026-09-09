import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icon";
import { Button, ErrorBanner, Spinner } from "../components/ui";
import { getErrorMessage } from "../lib/api-error";

export function LoginPage() {
  const { isAuthenticated, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { document.title = "Sign in — Tempo"; }, []);
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      await signIn(username, password);
      const destination = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/dashboard";
      navigate(destination, { replace: true });
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <section className="login-story">
        <div className="login-story__top"><div className="brand-mark brand-mark--light"><Icon name="calendar" /></div><strong>Tempo</strong></div>
        <div className="login-story__content">
          <span className="login-kicker"><Icon name="spark" /> Constraint-aware scheduling</span>
          <h1>Build a better week,<br />in a few clicks.</h1>
          <p>Turn courses, rooms, staff availability and student groups into a conflict-free university timetable.</p>
          <div className="login-proof">
            <div><Icon name="check" /><span><strong>Hard constraints</strong> checked automatically</span></div>
            <div><Icon name="check" /><span><strong>Room allocation</strong> optimized by capacity</span></div>
            <div><Icon name="check" /><span><strong>Ready to share</strong> with one-click CSV export</span></div>
          </div>
        </div>
        <p className="login-story__footer">University Timetable Optimizer · Bachelor thesis project</p>
      </section>
      <main className="login-panel">
        <div className="login-form-wrap">
          <div className="login-mobile-brand"><div className="brand-mark"><Icon name="calendar" /></div><strong>Tempo</strong></div>
          <p className="eyebrow">Welcome back</p>
          <h2>Sign in to your workspace</h2>
          <p className="login-subtitle">Use the administrator credentials configured in the backend.</p>
          <form onSubmit={handleSubmit} className="login-form">
            {error && <ErrorBanner message={error} />}
            <label><span>Username</span><div className="input-with-icon"><Icon name="users" /><input autoFocus autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Enter your username" required /></div></label>
            <label><span>Password</span><div className="input-with-icon"><Icon name="lock" /><input type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" required /><button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)}>{showPassword ? "Hide" : "Show"}</button></div></label>
            <Button type="submit" disabled={isSubmitting || !username || !password}>{isSubmitting ? <><Spinner small /> Signing in…</> : <>Sign in <Icon name="arrow" /></>}</Button>
          </form>
          <p className="login-help">Having trouble? Confirm that the FastAPI server is running on port 8000.</p>
        </div>
      </main>
    </div>
  );
}
