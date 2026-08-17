export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-6">
      <div className="h-0.5 w-10 bg-white/15" />
      <p className="mt-6 text-xl font-medium tracking-tight">{title}</p>
      <p className="mt-3 max-w-lg text-[15px] leading-6 text-white/45">{body}</p>
    </div>
  );
}
