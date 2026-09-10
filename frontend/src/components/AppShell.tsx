import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useGeneration } from "../generation/GenerationContext";
import { Icon, type IconName } from "./Icon";

const navigation: { to: string; label: string; icon: IconName }[] = [
  { to: "/generate", label: "Generate", icon: "spark" },
  { to: "/runs", label: "Run history", icon: "history" },
  { to: "/inputs", label: "Input data", icon: "settings" },
  { to: "/assignments", label: "Assignments", icon: "users" },
];

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

export function AppShell() {
  const { user, signOut } = useAuth();
  const generation = useGeneration();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const current = navigation.find((item) => location.pathname.startsWith(item.to));

  return (
    <div className="app-layout">
      <aside className={`sidebar${mobileOpen ? " sidebar--open" : ""}`}>
        <div className="sidebar__brand"><div className="brand-mark"><Icon name="calendar" /></div><div><strong>Time's UP</strong><span>Timetable optimizer</span></div><img className="sidebar__university-logo" src="/university-prishtina-logo.png" alt="University of Prishtina" /></div>
        <button className="sidebar__close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><Icon name="x" /></button>
        <nav className="sidebar__nav" aria-label="Main navigation">
          <p>Workspace</p>
          {navigation.map((item) => <NavLink key={item.to} to={item.to} onClick={() => setMobileOpen(false)} className={({ isActive }) => isActive ? "active" : ""}><Icon name={item.icon} /><span>{item.label}</span></NavLink>)}
        </nav>
        <div className="sidebar__footer"><div className="user-avatar">{user?.username.charAt(0).toUpperCase()}</div><div><strong>{user?.username}</strong><span>Administrator</span></div><button onClick={signOut} aria-label="Sign out" title="Sign out"><Icon name="logout" /></button></div>
      </aside>
      {mobileOpen && <button className="sidebar-overlay" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
      <main className="main-content">
        <div className="mobile-bar"><button onClick={() => setMobileOpen(true)} aria-label="Open menu"><Icon name="menu" /></button><strong>{current?.label ?? "Time's UP"}</strong><div className="user-avatar">{user?.username.charAt(0).toUpperCase()}</div></div>
        {generation.status !== "idle" && (
          <div
            className={`generation-strip generation-strip--${generation.status}`}
            role="status"
            aria-live="polite"
          >
            <div className="generation-strip__icon">
              <Icon name={generation.status === "succeeded" ? "check" : generation.status === "running" ? "clock" : "x"} />
            </div>
            <div className="generation-strip__copy">
              <strong>
                {generation.status === "running"
                  ? `Generating ${generation.facultyName} timetable`
                  : generation.status === "succeeded"
                    ? "Timetable ready"
                    : "Timetable generation failed"}
              </strong>
              <span>
                {generation.status === "running"
                  ? `${generation.stage} · ${formatElapsed(generation.elapsedSeconds)} elapsed`
                  : generation.status === "succeeded"
                    ? "Your timetable is ready to review."
                    : generation.errorMessage}
              </span>
            </div>
            {generation.status === "succeeded" && generation.results[0] && (
              <Link className="generation-strip__action" to="/generate">
                Review timetable <Icon name="arrow" />
              </Link>
            )}
            {generation.status === "running" && location.pathname !== "/generate" && (
              <Link className="generation-strip__action" to="/generate">
                View status <Icon name="arrow" />
              </Link>
            )}
            {generation.status !== "running" && (
              <button type="button" className="generation-strip__dismiss" onClick={generation.dismiss} aria-label="Dismiss notification">
                <Icon name="x" />
              </button>
            )}
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
