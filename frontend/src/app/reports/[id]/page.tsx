"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { fetchReport } from "@/lib/api";
import { splitSections } from "@/lib/parse-analysis";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const SECTIONS: Array<{
  key: "thesis" | "evidence" | "chainOfThought" | "riskAssessment" | "predictions";
  title: string;
}> = [
  { key: "thesis", title: "Thesis" },
  { key: "evidence", title: "Evidence" },
  { key: "chainOfThought", title: "Chain of Thought" },
  { key: "riskAssessment", title: "Risk Assessment" },
  { key: "predictions", title: "Predictions" },
];

function MarkdownBlock({ children }: { children: string }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none prose-headings:font-semibold prose-p:leading-relaxed prose-li:my-1">
      <ReactMarkdown>{children}</ReactMarkdown>
    </div>
  );
}

export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const reportId = Number(id);

  const { data: report, isLoading, isError } = useQuery({
    queryKey: ["report", reportId],
    queryFn: () => fetchReport(reportId),
    enabled: !isNaN(reportId),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (isError || !report) {
    return <p className="text-sm text-red-400">Report not found.</p>;
  }

  const sections = splitSections(report.analysis ?? "");
  const noSectionsMatched =
    !sections.remainder && SECTIONS.every(({ key }) => !sections[key]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{report.sector_name}</h1>
          <p className="text-sm text-muted-foreground">
            {new Date(report.created_at).toLocaleDateString("en-US", {
              month: "long",
              day: "numeric",
              year: "numeric",
            })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {report.validation_status && (
            <Badge variant="outline" className="capitalize">
              {report.validation_status}
            </Badge>
          )}
          {report.confidence_score != null && (
            <span className="text-sm text-muted-foreground">
              {Math.round(report.confidence_score * 100)}% confidence
            </span>
          )}
        </div>
      </div>

      {sections.remainder && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <MarkdownBlock>{sections.remainder}</MarkdownBlock>
          </CardContent>
        </Card>
      )}

      {SECTIONS.map(({ key, title }) =>
        sections[key] ? (
          <Card key={key}>
            <CardHeader>
              <CardTitle className="text-sm">{title}</CardTitle>
            </CardHeader>
            <CardContent>
              <MarkdownBlock>{sections[key] as string}</MarkdownBlock>
            </CardContent>
          </Card>
        ) : null,
      )}

      {noSectionsMatched && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            <MarkdownBlock>{report.analysis ?? ""}</MarkdownBlock>
          </CardContent>
        </Card>
      )}

      {report.news_summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">News Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <MarkdownBlock>{report.news_summary}</MarkdownBlock>
          </CardContent>
        </Card>
      )}

      {report.validation && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Validation Notes</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">{report.validation}</CardContent>
        </Card>
      )}

      {report.predictions.length > 0 && (
        <>
          <Separator />
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Predictions</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Ticker</TableHead>
                    <TableHead>AI direction</TableHead>
                    <TableHead>Price at report</TableHead>
                    <TableHead>Price 1w later</TableHead>
                    <TableHead>Correct</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.predictions.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="font-medium">{p.ticker}</TableCell>
                      <TableCell>{p.ai_direction ?? "—"}</TableCell>
                      <TableCell>{p.price_at_report?.toFixed(2) ?? "—"}</TableCell>
                      <TableCell>{p.price_1w_later?.toFixed(2) ?? "—"}</TableCell>
                      <TableCell>
                        {p.prediction_correct == null ? (
                          <span className="text-muted-foreground">pending</span>
                        ) : p.prediction_correct ? (
                          <span className="text-emerald-400">✓</span>
                        ) : (
                          <span className="text-red-400">✗</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
