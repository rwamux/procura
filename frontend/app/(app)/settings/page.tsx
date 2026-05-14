"use client";

import { useAuth } from "@/components/providers";
import { OPENROUTER_MODELS } from "@/types";

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-semibold mb-6">Settings</h1>

      <div className="space-y-5">
        <div className="border rounded-lg p-5">
          <h2 className="text-sm font-medium mb-4">Account</h2>
          <dl className="space-y-3 text-sm">
            <Row label="Name" value={user?.name ?? "—"} />
            <Row label="Email" value={user?.email ?? "—"} />
            <Row label="Role" value={user?.role ?? "—"} />
          </dl>
        </div>

        <div className="border rounded-lg p-5">
          <h2 className="text-sm font-medium mb-1">Available Models</h2>
          <p className="text-xs text-muted-foreground mb-4">
            Models available for selection when starting a workflow. Powered by OpenRouter.
          </p>
          <div className="space-y-2">
            {OPENROUTER_MODELS.map((m) => (
              <div key={m.id} className="flex items-center justify-between py-2 border-b last:border-0">
                <span className="text-sm font-medium">{m.label}</span>
                <span className="text-xs text-muted-foreground font-mono">{m.id}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
