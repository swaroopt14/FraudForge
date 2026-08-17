"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/blue-team", label: "Command" },
  { href: "/blue-team/detections", label: "Live detection" },
  { href: "/blue-team/attacks", label: "Attack intel" },
  { href: "/blue-team/network", label: "Network" },
  { href: "/blue-team/investigation", label: "Investigation" },
  { href: "/blue-team/mitigation", label: "Mitigation" },
  { href: "/blue-team/reports", label: "Reports" },
  { href: "/blue-team/evolution", label: "Evolution" },
];

export function BlueNav() {
  const path = usePathname();
  return (
    <div className="mb-10 border-b border-white/10">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/35">Blue team</p>
      <nav className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
        {LINKS.map((link) => {
          const active = path === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`pb-3 ${active ? "text-white" : "text-white/40 hover:text-white"}`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
