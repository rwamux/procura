import { Check } from "lucide-react";
import { ProcurementStage, STAGE_LABELS } from "@/types";
import { cn } from "@/lib/utils";

const STAGES: ProcurementStage[] = ["RFP", "PROPOSAL_INTAKE", "EVALUATION", "CONTRACT", "FINALIZED"];

const STAGE_COLORS: Record<ProcurementStage, string> = {
  RFP: "text-blue-600 border-blue-400 bg-blue-50",
  PROPOSAL_INTAKE: "text-violet-600 border-violet-400 bg-violet-50",
  EVALUATION: "text-amber-600 border-amber-400 bg-amber-50",
  CONTRACT: "text-orange-600 border-orange-400 bg-orange-50",
  FINALIZED: "text-emerald-600 border-emerald-400 bg-emerald-50",
};

const STAGE_DONE: Record<ProcurementStage, string> = {
  RFP: "bg-blue-500 border-blue-500 text-white",
  PROPOSAL_INTAKE: "bg-violet-500 border-violet-500 text-white",
  EVALUATION: "bg-amber-500 border-amber-500 text-white",
  CONTRACT: "bg-orange-500 border-orange-500 text-white",
  FINALIZED: "bg-emerald-500 border-emerald-500 text-white",
};

const CONNECTOR_DONE: Record<ProcurementStage, string> = {
  RFP: "bg-blue-300",
  PROPOSAL_INTAKE: "bg-violet-300",
  EVALUATION: "bg-amber-300",
  CONTRACT: "bg-orange-300",
  FINALIZED: "bg-emerald-300",
};

export function WorkflowStepper({ currentStage }: { currentStage: ProcurementStage }) {
  const currentIdx = STAGES.indexOf(currentStage);

  return (
    <div className="flex items-center">
      {STAGES.map((stage, i) => {
        const done = i < currentIdx;
        const active = i === currentIdx;

        return (
          <div key={stage} className="flex items-center">
            <div className="flex flex-col items-center">
              <div className={cn(
                "h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-all",
                done && STAGE_DONE[stage],
                active && STAGE_COLORS[stage],
                !done && !active && "border-border text-muted-foreground bg-background"
              )}>
                {done ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </div>
              <span className={cn(
                "text-[11px] mt-1.5 whitespace-nowrap font-medium",
                active ? "text-foreground" : done ? "text-muted-foreground" : "text-muted-foreground/60"
              )}>
                {STAGE_LABELS[stage]}
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <div className={cn(
                "h-0.5 w-12 mt-[-1.1rem] mx-1.5 rounded-full transition-all",
                i < currentIdx ? CONNECTOR_DONE[stage] : "bg-border"
              )} />
            )}
          </div>
        );
      })}
    </div>
  );
}
