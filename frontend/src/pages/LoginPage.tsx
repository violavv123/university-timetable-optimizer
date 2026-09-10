import { useEffect, useState, type SubmitEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icon";
import { Button, ErrorBanner } from "../components/ui";
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

  useEffect(() => { document.title = "Sign in — Time's UP"; }, []);
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
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
        <div className="login-story__top"><div className="brand-mark brand-mark--light"><Icon name="calendar" /></div><strong>Time's UP</strong></div>
        <div className="login-story__content">
          <span className="login-kicker"><Icon name="spark" /> University scheduling</span>
          <h1>Manage time<br />better.</h1>
          <p>Create, compare and publish conflict-free university timetables from one clear workspace.</p>
        </div>
        <p className="login-story__footer">University Timetable Optimizer · Bachelor thesis project</p>
      </section>
      <main className="login-panel">
        <img className="university-logo" src="/university-prishtina-logo.png" alt="University of Prishtina" />
        <div className="login-form-wrap">
          <div className="login-mobile-brand"><div className="brand-mark"><Icon name="calendar" /></div><strong>Time's UP</strong></div>
          <p className="eyebrow">Welcome back</p>
          <h2>Sign in</h2>
          <p className="login-subtitle">Enter the administrator credentials.</p>
          <form onSubmit={handleSubmit} className="login-form">
            {error && <ErrorBanner message={error} />}
            <label><span>Username</span><div className="input-with-icon"><Icon name="users" /><input autoFocus autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Enter your username" required /></div></label>
            <label><span>Password</span><div className="input-with-icon"><Icon name="lock" /><input type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" required /><button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)}>{showPassword ? "Hide" : "Show"}</button></div></label>
            <Button type="submit" disabled={isSubmitting || !username || !password}>{isSubmitting ? "Signing in…" : <>Sign in <Icon name="arrow" /></>}</Button>
          </form>
        </div>
      </main>
    </div>
  );
}
