import React, { useState, useEffect } from "react";

interface LoginScreenProps {
  onAuthenticated?: (token: string) => void;
  title?: string;
  subtitle?: string;
  children?: React.ReactNode;
}

/**
 * React Component for password-protected authentication.
 * Verifies password against the server-side APP_PASSWORD environment variable via /api/auth/login.
 * Once verified, renders the main application dashboard or triggers onAuthenticated.
 */
export const LoginScreen: React.FC<LoginScreenProps> = ({
  onAuthenticated,
  title = "System Locked",
  subtitle = "Enter the password to access GigCraft Studio, Market Intelligence, and AI tools.",
  children,
}) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Check existing session on mount
  useEffect(() => {
    let isMounted = true;
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem("gigcraft_auth_token");
        const headers: HeadersInit = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        const res = await fetch("/api/auth/status", { headers });
        const data = await res.json().catch(() => ({}));
        if (isMounted) {
          if (res.ok && data.authenticated) {
            setIsAuthenticated(true);
            if (token && onAuthenticated) onAuthenticated(token);
          } else {
            setIsAuthenticated(false);
          }
        }
      } catch {
        if (isMounted) setIsAuthenticated(false);
      }
    };
    checkAuth();
    return () => {
      isMounted = false;
    };
  }, [onAuthenticated]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim()) return;

    setError(null);
    setLoading(true);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: password.trim() }),
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok && data.success && data.token) {
        try {
          localStorage.setItem("gigcraft_auth_token", data.token);
        } catch {}
        setIsAuthenticated(true);
        if (onAuthenticated) {
          onAuthenticated(data.token);
        }
      } else {
        setError(data.detail || "Incorrect password. Please try again.");
      }
    } catch {
      setError("Unable to connect to authentication server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      const token = localStorage.getItem("gigcraft_auth_token");
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch {}
    try {
      localStorage.removeItem("gigcraft_auth_token");
    } catch {}
    setIsAuthenticated(false);
    setPassword("");
  };

  // If already authenticated and children are provided, render the main dashboard
  if (isAuthenticated && children) {
    return (
      <div className="authenticated-app-container">
        {children}
      </div>
    );
  }

  // If initial auth check is in progress, display a minimal neutral loader
  if (isAuthenticated === null) {
    return (
      <div className="login-stage" style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "var(--muted, #64748b)", fontSize: "14px", fontWeight: 500 }}>
          Checking access permissions…
        </div>
      </div>
    );
  }

  return (
    <div className="login-stage" id="loginScreenContainer">
      <div className="login-card" id="loginCard">
        <div className="login-head">
          <div className="login-badge">
            <span role="img" aria-label="locked">🔒</span>
            <span>Protected Workspace</span>
          </div>
          <div className="login-brand">
            <div className="brand" style={{ marginRight: 0 }}>
              <span className="mark">G</span>
              <div className="brand-text" style={{ textAlign: "left" }}>
                <strong className="brand-name">GigCraft</strong>
                <small className="brand-sub">Access Control</small>
              </div>
            </div>
          </div>
          <h1 id="loginTitle">{title}</h1>
          <p>{subtitle}</p>
        </div>

        <form id="loginForm" className="login-form" onSubmit={handleSubmit}>
          {error && (
            <div className="login-error show" id="loginError" role="alert">
              {error}
            </div>
          )}

          <div className="field">
            <label htmlFor="passwordInput">System Password</label>
            <div className="input-with-action">
              <input
                type={showPassword ? "text" : "password"}
                id="passwordInput"
                name="password"
                className="input"
                placeholder="Enter system password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                autoFocus
              />
              <button
                type="button"
                id="togglePwd"
                className="toggle-pwd-btn"
                onClick={() => setShowPassword(!showPassword)}
                title={showPassword ? "Hide password" : "Show password"}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "🔒" : "👁️"}
              </button>
            </div>
          </div>

          <button
            type="submit"
            id="submitBtn"
            className="login-btn"
            disabled={loading}
          >
            {loading && <span className="btn-spinner" aria-hidden="true" />}
            <span id="btnText">
              {loading ? "Verifying credentials…" : "Unlock System →"}
            </span>
          </button>
        </form>

        <div className="login-footer">
          <span>Protected Workspace • GigCraft</span>
        </div>
      </div>
    </div>
  );
};

export default LoginScreen;
