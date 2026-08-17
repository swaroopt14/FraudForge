"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Command center" },
  { href: "/red-team", label: "Red team" },
  { href: "/blue-team", label: "Blue team" },
  { href: "/explorer", label: "Explorer" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-20 border-b border-white/10 bg-ink/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-end justify-between px-6 py-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-signal">Payment defense</p>
          <p className="mt-1 text-sm text-white/70">Adversarial lab</p>
        </div>
        <nav className="flex gap-8 text-sm">
          {LINKS.map((link) => {
            const active = link.href === "/blue-team" ? path.startsWith("/blue-team") : path === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`relative pb-1 transition-colors ${active ? "text-white" : "text-white/45 hover:text-white"}`}
              >
                {link.label}
                <span
                  className={`absolute inset-x-0 -bottom-px h-px bg-signal transition-opacity ${active ? "opacity-100" : "opacity-0"}`}
                />
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
