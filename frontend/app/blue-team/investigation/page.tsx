"use client";

import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { api, type BlueEntity, type BlueTimelineEvent } from "@/lib/api";
import { familyLabel, inr, num } from "@/lib/format";

const TYPES = ["beneficiary", "customer", "device", "ip", "transaction"] as const;

function clock(ts: number) {
  const t = Math.abs(Math.floor(ts)) % 86400;
  const h = String(Math.floor(t / 3600)).padStart(2, "0");
  const m = String(Math.floor((t % 3600) / 60)).padStart(2, "0");
  const s = String(t % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

export default function Investigation() {
  const [entityType, setEntityType] = useState<(typeof TYPES)[number]>("beneficiary");
  const [entityId, setEntityId] = useState("");
  const [profile, setProfile] = useState<BlueEntity | null>(null);
  const [events, setEvents] = useState<BlueTimelineEvent[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function search() {
    if (!entityId.trim()) return;
    setBusy(true);
    setError("");
    try {
      const id = entityId.trim();
      const body = await api<BlueEntity>(`/blue/entities/${entityType}/${encodeURIComponent(id)}`);
      setProfile(body);
      if (entityType !== "transaction") {
        const tl = await api<{ events: BlueTimelineEvent[] }>(
          `/blue/entities/${entityType}/${encodeURIComponent(id)}/timeline`,
        );
        setEvents(tl.events);
      } else {
        setEvents([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rise space-y-12">
      <div>
        <h1 className="text-4xl font-medium tracking-tight">Investigation</h1>
        <p className="mt-2 max-w-xl text-sm text-white/55">Move from a scored row to the entity and its timeline.</p>
      </div>
      <form
        className="grid gap-6 sm:grid-cols-[10rem_1fr_8rem]"
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
      >
        <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
          Entity
          <select
            className="mt-2 w-full border-b border-white/20 bg-transparent py-2 text-sm outline-none"
            value={entityType}
            onChange={(e) => setEntityType(e.target.value as (typeof TYPES)[number])}
          >
            {TYPES.map((t) => (
              <option key={t} value={t} className="bg-ink">
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-xs uppercase tracking-[0.16em] text-white/40">
          Identifier
          <input
            className="mt-2 w-full border-b border-white/20 bg-transparent py-2 font-mono text-sm outline-none"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            placeholder="BEN-882"
          />
        </label>
        <button type="submit" disabled={busy} className="self-end bg-signal py-3 text-sm font-medium text-ink disabled:opacity-40">
          {busy ? "Looking…" : "Search"}
        </button>
      </form>
      {error ? <p className="font-mono text-sm text-signal">{error}</p> : null}
      {!profile ? (
        <EmptyState title="No entity loaded" body="Search a beneficiary, customer, device, or IP from the current stream." />
      ) : !profile.found ? (
        <EmptyState title="Not on this stream" body={profile.reason || "That identifier is not in the latest Blue ingest."} />
      ) : (
        <>
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Entity profile</h2>
            <p className="mt-3 font-mono text-lg">
              {familyLabel(profile.entity_type)} {profile.entity_id}
            </p>
            <dl className="mt-6 grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-5">
              {[
                ["Connected accounts", num(profile.connected_accounts)],
                ["Devices", num(profile.devices)],
                ["IPs", num(profile.ips)],
                ["Transactions", num(profile.transactions)],
                ["Total value", inr(profile.total_value)],
              ].map(([k, v]) => (
                <div key={k} className="border-t border-white/10 pt-3">
                  <dt className="text-xs text-white/45">{k}</dt>
                  <dd className="mt-1 font-mono text-2xl">{v}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">Timeline</h2>
            {events.length === 0 ? (
              <p className="mt-4 text-sm text-white/40">No events for this entity.</p>
            ) : (
              <ul className="mt-4">
                {events.map((ev, i) => (
                  <li key={`${ev.transaction_id}-${i}`} className="grid grid-cols-[4.5rem_1fr] gap-4 border-t border-white/10 py-3 text-sm">
                    <span className="font-mono text-white/45">{clock(ev.timestamp)}</span>
                    <span>
                      {ev.customer_id} → {ev.beneficiary_id}
                      <span className="ml-3 font-mono text-white/40">{inr(ev.amount)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
