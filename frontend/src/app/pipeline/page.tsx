import { PipelineRunner } from "@/components/PipelineRunner";

export const metadata = { title: "Pipeline — Market Intelligence" };

export default function PipelinePage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Pipeline</h1>
        <p className="text-sm text-muted-foreground">
          Trigger a new sector analysis and watch it run live.
        </p>
      </div>
      <PipelineRunner />
    </div>
  );
}
