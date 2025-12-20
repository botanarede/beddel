"use client";

import { useState, useRef, useEffect } from "react";
import { Bug, X, Sparkles } from "lucide-react";
import { Card } from "@/src/components/ui/card";
import { ScrollArea } from "@/src/components/ui/scroll-area";
import { Skeleton } from "@/src/components/ui/skeleton";
import { Button } from "@/src/components/ui/button";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/src/components/ui/resizable";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { DebugSidebar } from "./DebugSidebar";
import { sendChatMessage } from "@/src/lib/chat-api";
import type { ConversationMessage, ExecutionStep } from "beddel";

export function ChatInterface() {
  const [messages, setMessages] = useState<ConversationMessage[]>([
    { role: "assistant", content: "Olá! Sou seu assistente de IA powered by Beddel. Como posso ajudar?" },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [totalDuration, setTotalDuration] = useState<number | undefined>();
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSendMessage = async (content: string) => {
    const userMessage: ConversationMessage = { role: "user", content };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setExecutionSteps([]);
    setTotalDuration(undefined);

    try {
      const allMessages = [...messages, userMessage];
      const response = await sendChatMessage(allMessages);

      if (response.success && response.data) {
        const assistantMessage: ConversationMessage = { role: "assistant", content: response.data.response };
        setMessages((prev) => [...prev, assistantMessage]);
        if (response.data.execution_steps) setExecutionSteps(response.data.execution_steps);
        if (response.data.total_duration !== undefined) setTotalDuration(response.data.total_duration);
      } else {
        const errorMessage: ConversationMessage = { role: "assistant", content: `Erro: ${response.error || "Erro desconhecido"}` };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Erro desconhecido";
      const errorMessage: ConversationMessage = { role: "assistant", content: `Erro: ${message}` };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="h-screen p-4">
      {/* Desktop: Resizable panels */}
      <div className="hidden lg:block h-full">
        <ResizablePanelGroup direction="horizontal" className="h-full rounded-lg">
          <ResizablePanel defaultSize={65} minSize={40}>
            <Card className="h-full flex flex-col glass-card border-border/50 overflow-hidden">
              {/* Header */}
              <div className="p-6 border-b border-border/50">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-xl bg-primary/10">
                    <Sparkles className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
                      Beddel Chat
                    </h1>
                    <p className="text-sm text-muted-foreground">AI-powered Q&A Assistant</p>
                  </div>
                </div>
              </div>

              {/* Messages */}
              <ScrollArea className="flex-1 p-6">
                <div className="space-y-4">
                  {messages.map((message, index) => (
                    <ChatMessage key={index} message={message} />
                  ))}
                  {isLoading && (
                    <div className="flex gap-4 mb-6">
                      <Skeleton className="h-8 w-8 rounded-full" />
                      <div className="space-y-2 flex-1">
                        <Skeleton className="h-4 w-3/4" />
                        <Skeleton className="h-4 w-1/2" />
                      </div>
                    </div>
                  )}
                  <div ref={scrollRef} />
                </div>
              </ScrollArea>

              {/* Input */}
              <div className="p-4 border-t border-border/50">
                <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
              </div>
            </Card>
          </ResizablePanel>

          <ResizableHandle withHandle />

          <ResizablePanel defaultSize={35} minSize={25}>
            <div className="h-full pl-4">
              <DebugSidebar executionSteps={executionSteps} totalDuration={totalDuration} isLoading={isLoading} />
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      {/* Mobile: Stacked with toggle */}
      <div className="lg:hidden h-full flex flex-col">
        <Card className="flex-1 flex flex-col glass-card border-border/50 overflow-hidden">
          <div className="p-4 border-b border-border/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
                Beddel Chat
              </h1>
            </div>
            <Button variant="outline" size="sm" onClick={() => setShowMobileSidebar(true)} className="gap-2">
              <Bug className="h-4 w-4" />
              Debug
            </Button>
          </div>

          <ScrollArea className="flex-1 p-4">
            <div className="space-y-4">
              {messages.map((message, index) => (
                <ChatMessage key={index} message={message} />
              ))}
              {isLoading && (
                <div className="flex gap-4 mb-6">
                  <Skeleton className="h-8 w-8 rounded-full" />
                  <div className="space-y-2 flex-1">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-1/2" />
                  </div>
                </div>
              )}
              <div ref={scrollRef} />
            </div>
          </ScrollArea>

          <div className="p-4 border-t border-border/50">
            <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
          </div>
        </Card>

        {/* Mobile sidebar overlay */}
        {showMobileSidebar && (
          <div className="fixed inset-0 z-50">
            <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setShowMobileSidebar(false)} />
            <div className="absolute right-0 top-0 bottom-0 w-[90vw] max-w-[400px] p-4">
              <div className="relative h-full">
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute -left-12 top-2 z-10 bg-background/80 rounded-full"
                  onClick={() => setShowMobileSidebar(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
                <DebugSidebar executionSteps={executionSteps} totalDuration={totalDuration} isLoading={isLoading} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
