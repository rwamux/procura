"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

interface Criterion {
  criterion: string;
  weight: number;
}

export default function NewProcurementPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [title, setTitle] = useState("");
  const [objective, setObjective] = useState("");
  const [scope, setScope] = useState("");
  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [timeline, setTimeline] = useState("");
  const [compliance, setCompliance] = useState("");
  const [criteria, setCriteria] = useState<Criterion[]>([
    { criterion: "Technical Fit", weight: 0.4 },
    { criterion: "Cost", weight: 0.3 },
    { criterion: "Delivery Timeline", weight: 0.15 },
    { criterion: "Risk", weight: 0.15 },
  ]);

  const weightSum = criteria.reduce((s, c) => s + c.weight, 0);
  const weightOk = Math.abs(weightSum - 1) < 0.01;

  function addCriterion() {
    setCriteria([...criteria, { criterion: "", weight: 0 }]);
  }

  function removeCriterion(i: number) {
    setCriteria(criteria.filter((_, idx) => idx !== i));
  }

  function updateCriterion(i: number, field: keyof Criterion, value: string) {
    setCriteria(criteria.map((c, idx) =>
      idx === i ? { ...c, [field]: field === "weight" ? parseFloat(value) || 0 : value } : c
    ));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!weightOk) {
      setError("Evaluation criteria weights must sum to 1.0");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const p = await api.procurements.create({
        title,
        business_objective: objective,
        scope,
        budget_min: budgetMin ? parseFloat(budgetMin) : null,
        budget_max: budgetMax ? parseFloat(budgetMax) : null,
        budget_currency: currency,
        timeline,
        evaluation_criteria: criteria,
        compliance_requirements: compliance || null,
      });
      router.push(`/procurements/${p.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create procurement");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <Link href="/procurements" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
        <ArrowLeft className="h-3.5 w-3.5" /> Procurements
      </Link>
      <h1 className="text-2xl font-semibold mb-6">New Procurement</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Section title="Basic Information">
          <Field label="Procurement Title" required>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="e.g. Cloud Infrastructure Migration" className={inputClass} />
          </Field>
          <Field label="Business Objective" required>
            <textarea value={objective} onChange={(e) => setObjective(e.target.value)} required rows={3} placeholder="What business problem does this solve?" className={inputClass} />
          </Field>
          <Field label="Scope of Work" required>
            <textarea value={scope} onChange={(e) => setScope(e.target.value)} required rows={4} placeholder="Describe the scope, deliverables, and boundaries..." className={inputClass} />
          </Field>
        </Section>

        <Section title="Budget & Timeline">
          <div className="grid grid-cols-3 gap-3">
            <Field label="Min Budget">
              <input type="number" value={budgetMin} onChange={(e) => setBudgetMin(e.target.value)} placeholder="0" className={inputClass} />
            </Field>
            <Field label="Max Budget">
              <input type="number" value={budgetMax} onChange={(e) => setBudgetMax(e.target.value)} placeholder="0" className={inputClass} />
            </Field>
            <Field label="Currency">
              <select value={currency} onChange={(e) => setCurrency(e.target.value)} className={inputClass}>
                <option>USD</option><option>EUR</option><option>GBP</option><option>ZAR</option>
              </select>
            </Field>
          </div>
          <Field label="Timeline" required>
            <input value={timeline} onChange={(e) => setTimeline(e.target.value)} required placeholder="e.g. 6 months, Q3 2026" className={inputClass} />
          </Field>
        </Section>

        <Section title="Evaluation Criteria">
          <p className="text-xs text-muted-foreground mb-3">
            Weights must sum to 1.0. Current: <span className={weightOk ? "text-green-600 font-medium" : "text-destructive font-medium"}>{weightSum.toFixed(2)}</span>
          </p>
          <div className="flex gap-2 items-center mb-1 px-0.5">
            <span className="flex-1 text-xs text-muted-foreground">Criterion name</span>
            <span className="w-20 text-xs text-muted-foreground text-center">Weight (0–1)</span>
            <span className="w-6" />
          </div>
          <div className="space-y-2">
            {criteria.map((c, i) => (
              <div key={i} className="flex gap-2 items-center">
                <input value={c.criterion} onChange={(e) => updateCriterion(i, "criterion", e.target.value)} placeholder="Criterion name" className={`${inputClass} flex-1`} />
                <input type="number" value={c.weight} onChange={(e) => updateCriterion(i, "weight", e.target.value)} step="0.05" min="0" max="1" className="w-20 px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring bg-background text-foreground" />
                <button type="button" onClick={() => removeCriterion(i)} className="p-1.5 text-muted-foreground hover:text-destructive transition-colors">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
          <button type="button" onClick={addCriterion} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mt-2">
            <Plus className="h-3.5 w-3.5" /> Add criterion
          </button>
        </Section>

        <Section title="Compliance (optional)">
          <Field label="Compliance Requirements">
            <textarea value={compliance} onChange={(e) => setCompliance(e.target.value)} rows={3} placeholder="Legal, regulatory, or compliance requirements..." className={inputClass} />
          </Field>
        </Section>

        {error && <p className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md">{error}</p>}

        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={loading || !weightOk} className="px-5 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors">
            {loading ? "Creating..." : "Create Procurement"}
          </button>
          <Link href="/procurements" className="px-5 py-2 border rounded-md text-sm font-medium hover:bg-muted/50 transition-colors">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}

const inputClass = "w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring bg-background text-foreground";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border rounded-lg p-5">
      <h3 className="text-sm font-medium mb-4">{title}</h3>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1.5">
        {label}{required && <span className="text-destructive ml-1">*</span>}
      </label>
      {children}
    </div>
  );
}
