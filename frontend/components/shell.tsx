"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const GROUPS = [
  {
    label: "",
    items: [{ href: "/", label: "Command Center" }],
  },
  {
    label: "Red Team",
    items: [
      { href: "/threats", label: "Threat Library" },
      { href: "/red-team", label: "Generate" },
      { href: "/red-team/runs", label: "Attack Runs" },
      { href: "/red-team/reports", label: "Attack Reports" },
    ],
  },
  {
    label: "Blue Team",
    items: [
      { href: "/blue-team", label: "Defense Center" },
      { href: "/blue-team/detections", label: "Live Detection" },
      { href: "/blue-team/attacks", label: "Attack Intel" },
      { href: "/blue-team/network", label: "Network Intelligence" },
      { href: "/blue-team/investigation", label: "Investigation" },
      { href: "/blue-team/mitigation", label: "Mitigation" },
      { href: "/blue-team/cases", label: "Stopped / Bypassed" },
      { href: "/blue-team/reports", label: "Defense Reports" },
      { href: "/blue-team/evolution", label: "Model Evolution" },
      { href: "/explorer", label: "Transaction Explorer" },
      { href: "/blue-team/performance", label: "Training & Evaluation" },
    ],
  },
  {
    label: "Loop",
    items: [
      { href: "/loop", label: "Adversarial Round" },
      { href: "/evaluation", label: "Red vs Blue" },
      { href: "/evaluation/benchmarks", label: "Benchmarks" },
      { href: "/evaluation/versions", label: "Model Versions" },
    ],
  },
];

function active(path: string, href: string) {
  if (href === "/") return path === "/";
  if (href === "/red-team" || href === "/blue-team" || href === "/evaluation" || href === "/loop") {
    return path === href;
  }
  return path === href || path.startsWith(`${href}/`);
}

export function Shell() {
  const path = usePathname();
  return (
    <aside className="sticky top-0 flex h-screen w-[220px] shrink-0 flex-col border-r border-white/10 bg-ink px-4 py-6">
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-signal">Adversarial</p>
      <p className="mt-1 text-[13px] leading-5 text-white/80">Payment Defense Lab</p>
      <nav className="mt-8 flex-1 space-y-6 overflow-y-auto">
        {GROUPS.map((group) => (
          <div key={group.label || "root"}>
            {group.label ? (
              <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-white/30">{group.label}</p>
            ) : null}
            <ul className="space-y-1">
              {group.items.map((item) => {
                const on = active(path, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={`block px-1 py-1.5 text-[13px] ${on ? "text-signal" : "text-white/55 hover:text-white"}`}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/25">P2 · graph features</p>
    </aside>
  );
}
