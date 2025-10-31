"use client";

import "./globals.css";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Provider } from "react-redux";
import { makeStore } from "../redux/store";

const tabs = [
  { href: "/", label: "Home" },
  { href: "/bid-comp", label: "Bid Comp" },
  { href: "/pdf-to-esx", label: "PDF to ESX" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const store = makeStore();
  const pathname = usePathname();

  return (
    <html lang="en">
      <body className="bg-slate-100 text-gray-900">
        <Provider store={store}>
          <div className="flex min-h-screen flex-col">
            <header className="border-b bg-white">
              <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
                <span className="text-lg font-semibold tracking-tight">VIP Claims Dashboard</span>
                <nav className="flex gap-2">
                  {tabs.map((tab) => {
                    const isActive =
                      tab.href === "/"
                        ? pathname === tab.href
                        : pathname.startsWith(tab.href);

                    return (
                      <Link
                        key={tab.href}
                        href={tab.href}
                        className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                          isActive
                            ? "bg-blue-600 text-white shadow-sm"
                            : "text-gray-600 hover:bg-gray-100"
                        }`}
                      >
                        {tab.label}
                      </Link>
                    );
                  })}
                </nav>
              </div>
            </header>
            <main className="flex-1">
              <div className="mx-auto w-full max-w-6xl px-6 py-10">{children}</div>
            </main>
          </div>
        </Provider>
      </body>
    </html>
  );
}


