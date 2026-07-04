import { PipelineRunner } from "@/components/PipelineRunner";

export const metadata = { title: "Analysis Pipeline - MarketPulse" };

export default function PipelinePage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Analysis Pipeline</h1>
        <p className="text-sm text-muted-foreground">
          Trigger a ticker analysis and inspect each LangGraph stage from evidence intake to signal-card packaging.
        </p>
      </div>
      <PipelineRunner />
    </div>
  );
}
