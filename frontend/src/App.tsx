import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppShell } from "./components/AppShell";
import { GeneratePage } from "./pages/GeneratePage";
import { LoginPage } from "./pages/LoginPage";
import { InputManagementPage } from "./pages/InputManagementPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { RunsPage } from "./pages/RunsPage";
import { SessionAssignmentsPage } from "./pages/SessionAssignmentsPage";
import { TimetablePage } from "./pages/TimetablePage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/generate" replace />} />
          <Route path="/generate" element={<GeneratePage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/runs/:runId" element={<TimetablePage />} />
          <Route path="/inputs/:resourceKey?" element={<InputManagementPage />} />
          <Route path="/assignments" element={<SessionAssignmentsPage />} />
          <Route path="/dashboard" element={<Navigate to="/generate" replace />} />
          <Route path="/data" element={<Navigate to="/generate" replace />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
