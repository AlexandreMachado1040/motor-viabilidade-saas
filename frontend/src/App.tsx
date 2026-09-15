import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { EstudoProvider } from "./estudo/EstudoContext";
import { AdminPage } from "./pages/AdminPage";
import { CallbackPage } from "./pages/CallbackPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { LoadPage } from "./pages/modulos/LoadPage";
import { SummaryPage } from "./pages/modulos/SummaryPage";

export default function App() {
  return (
    <AuthProvider>
      <EstudoProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<CallbackPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute apenasAdmin>
                <AdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/modulos/load"
            element={
              <ProtectedRoute modulo="load">
                <LoadPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/modulos/summary"
            element={
              <ProtectedRoute modulo="summary">
                <SummaryPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      </EstudoProvider>
    </AuthProvider>
  );
}
