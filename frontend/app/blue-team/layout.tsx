import { BlueNav } from "@/components/blue-nav";

export default function BlueLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <BlueNav />
      {children}
    </div>
  );
}
