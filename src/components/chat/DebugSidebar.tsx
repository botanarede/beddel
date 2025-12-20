"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Badge } from "@/src/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/src/components/ui/tabs";
import { ScrollArea } from "@/src/components/ui/scroll-area";
import { Separator } from "@/src/components/ui/separator";
import { Skeleton } from "@/src/components/ui/skeleton";
import { Clock, CheckCircle2, XCircle, Loader2, Zap, Database, Brain, Search } from "lucide-react";
import type { ExecutionStep } from "beddel";

interface DebugSidebarProps {
  executionSteps: ExecutionStep[];
  totalDuration?: number;
  isLoading: boolean;
}

const phaseIcons: Record<string, React.ReactNode> = {
  vectorization: <Zap className="h-3 w-3" />,
  storage: <Database className="h-3 w-3" />,
  retrieval: <Search className="h-3 w-3" />,
  generation: <Brain className="h-3 w-3" />,
};

const phaseColors: Record<string, string> = {
  vectorization: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  storage: "bg-green-500/20 text-green-400 border-green-500/30",
  retrieval: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  generation: "bg-orange-500/20 text-orange-400 border-orange-500/30",
};

function StatusIcon({ status }: { status: ExecutionStep["status"] }) {
  switch (status) {
    case "success": return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "error": return <XCircle className="h-4 w-4 text-red-500" />;
    case "running": return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    default: return <Clock className="h-4 w-4 text-muted-foreground" />;
  }
}

export function DebugSidebar({ executionSteps, totalDuration, isLoading }: DebugSidebarProps) {
  return (
    <Card className="h-full glass-card border-border/50 flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Zap className="h-5 w-5 text-primary" />
          Execution Debug
        </CardTitle>
        {totalDuration !== undefined && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            Total: {totalDuration}ms
          </div>
        )}
      </CardHeader>

      <Separator />

      <CardContent className="flex-1 p-0 overflow-hidden">
        <Tabs defaultValue="steps" className="h-full flex flex-col">
          <TabsList className="w-full justify-start rounded-none border-b bg-transparent p-0">
            <TabsTrigger value="steps" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary">
              Steps
            </TabsTrigger>
            <TabsTrigger value="timeline" className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary">
              Timeline
            </TabsTrigger>
          </TabsList>

          <TabsContent value="steps" className="flex-1 m-0 overflow-hidden">
            <ScrollArea className="h-full p-4">
              {isLoading && executionSteps.length === 0 ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-center gap-3">
                      <Skeleton className="h-8 w-8 rounded-full" />
                      <div className="space-y-2 flex-1">
                        <Skeleton className="h-4 w-3/4" />
                        <Skeleton className="h-3 w-1/2" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : executionSteps.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  Envie uma mensagem para ver os passos de execução
                </p>
              ) : (
                <div className="space-y-3">
                  {executionSteps.map((step, index) => (
                    <div key={index} className="p-3 rounded-lg bg-background/50 border border-border/50">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <StatusIcon status={step.status} />
                          <span className="font-medium text-sm">{step.agent}</span>
                        </div>
                        {step.phase && (
                          <Badge variant="outline" className={`text-xs ${phaseColors[step.phase] || ""}`}>
                            {phaseIcons[step.phase]} {step.phase}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">{step.action}</p>
                      {step.duration && (
                        <p className="text-xs text-muted-foreground mt-1">{step.duration}ms</p>
                      )}
                      {step.error && (
                        <p className="text-xs text-red-400 mt-1">{step.error}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </TabsContent>

          <TabsContent value="timeline" className="flex-1 m-0 overflow-hidden">
            <ScrollArea className="h-full p-4">
              {executionSteps.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  Nenhum dado de timeline disponível
                </p>
              ) : (
                <div className="relative pl-6">
                  <div className="absolute left-2 top-0 bottom-0 w-px bg-border" />
                  {executionSteps.map((step, index) => (
                    <div key={index} className="relative pb-4">
                      <div className="absolute left-[-18px] w-3 h-3 rounded-full bg-primary border-2 border-background" />
                      <div className="text-sm font-medium">{step.agent}</div>
                      <div className="text-xs text-muted-foreground">{step.action}</div>
                      {step.duration && (
                        <div className="text-xs text-primary">{step.duration}ms</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
