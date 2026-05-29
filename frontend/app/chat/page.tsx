"use client";

import { useState } from "react";
import SchemaExplorer from "@/components/SchemaExplorer";
import ChatThread from "@/components/ChatThread";
import SQLPanel from "@/components/SQLPanel";

export default function ChatPage() {
  const [schema, setSchema] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [currentSql, setCurrentSql] = useState<string>("");
  const [currentResult, setCurrentResult] = useState<any>(null);

  return (
    <div
      className="h-screen flex overflow-hidden"
      style={{ backgroundColor: "#080c10", color: "#e8edf2" }}
    >
      <SchemaExplorer schema={schema} setSchema={setSchema} />
      <ChatThread 
        messages={messages} 
        setMessages={setMessages}
        setCurrentSql={setCurrentSql}
        setCurrentResult={setCurrentResult}
      />
      <SQLPanel sql={currentSql} result={currentResult} />
    </div>
  );
}
