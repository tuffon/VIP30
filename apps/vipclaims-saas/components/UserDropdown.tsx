"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type UserDropdownProps = {
  email: string;
  onSignOut: () => void;
};

function truncateEmail(value: string) {
  if (value.length <= 24) return value;
  return `${value.slice(0, 21)}...`;
}

export function UserDropdown({ email, onSignOut }: UserDropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current) return;
      if (event.target instanceof Node && !containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
      >
        {truncateEmail(email)}
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-30 mt-2 min-w-[220px] rounded-lg border border-slate-200 bg-white py-2 shadow-lg"
        >
          <p className="px-4 py-2 text-sm text-slate-600">{email}</p>
          <div className="my-1 border-t border-slate-100" />
          <Link
            href="#"
            role="menuitem"
            title="Coming soon"
            onClick={(event) => event.preventDefault()}
            className="block px-4 py-2 text-sm text-slate-700 transition hover:bg-slate-50"
          >
            Settings (Coming soon)
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
            className="block w-full px-4 py-2 text-left text-sm text-rose-600 transition hover:bg-rose-50"
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
