import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  accessToken,
  fetchCurrentUser,
  signInRequest,
} from "../services/auth.service";
import type { CurrentUser } from "../types";

interface AuthContextValue {
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isInitializing, setIsInitializing] = useState(Boolean(accessToken.get()));

  const signOut = useCallback(() => {
    accessToken.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    const token = accessToken.get();
    if (!token) {
      setIsInitializing(false);
      return;
    }
    fetchCurrentUser()
      .then(setUser)
      .catch(signOut)
      .finally(() => setIsInitializing(false));
  }, [signOut]);

  useEffect(() => {
    window.addEventListener("auth:expired", signOut);
    return () => window.removeEventListener("auth:expired", signOut);
  }, [signOut]);

  const signIn = useCallback(async (username: string, password: string) => {
    const token = await signInRequest(username, password);
    accessToken.set(token);
    try {
      setUser(await fetchCurrentUser());
    } catch (error) {
      accessToken.clear();
      throw error;
    }
  }, []);

  const value = useMemo(
    () => ({ user, isAuthenticated: Boolean(user), isInitializing, signIn, signOut }),
    [user, isInitializing, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
