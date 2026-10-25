import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { tokenStore } from "@/api/client";
import { authApi } from "@/api/endpoints";
import type { TokenResponse, User } from "@/api/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; name: string; password: string; gitlab_username?: string }) => Promise<void>;
  updateProfile: (data: { name?: string; gitlab_username?: string | null }) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  const accept = (res: TokenResponse) => {
    tokenStore.set(res.access_token);
    setUser(res.user);
  };

  const value: AuthContextValue = {
    user,
    loading,
    login: async (email, password) => accept(await authApi.login({ email, password })),
    register: async (data) => accept(await authApi.register(data)),
    updateProfile: async (data) => {
      const updated = await authApi.updateMe(data);
      setUser(updated);
      return updated;
    },
    logout: () => {
      tokenStore.clear();
      setUser(null);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
