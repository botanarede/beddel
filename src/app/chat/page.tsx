"use client";

import { ChatInterface } from "@/src/components/chat/ChatInterface";

export default function ChatPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5">
      <ChatInterface />
    </main>
  );
}
