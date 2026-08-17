"use client";

export default function ErrorView({ error }: { error: Error }) {
  return (
    <p className="font-mono text-sm text-signal">
      {error.message || "Something failed."}
    </p>
  );
}
