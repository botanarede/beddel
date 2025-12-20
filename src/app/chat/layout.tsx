import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Beddel Chat - Q&A Assistant",
  description: "A modern chat interface powered by Beddel AI",
};

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
