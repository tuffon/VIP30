"use client";

import { ReactNode, useMemo } from "react";
import { Provider } from "react-redux";
import { SessionProvider } from "next-auth/react";
import { makeStore } from "../../redux/store";

export function AppProviders({ children }: { children: ReactNode }) {
  const store = useMemo(() => makeStore(), []);
  return (
    <SessionProvider>
      <Provider store={store}>{children}</Provider>
    </SessionProvider>
  );
}

