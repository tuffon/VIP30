"use client";

import "./globals.css";
import { Provider } from "react-redux";
import { makeStore } from "../redux/store";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const store = makeStore();
  return (
    <html lang="en">
      <body>
        <Provider store={store}>{children}</Provider>
      </body>
    </html>
  );
}


