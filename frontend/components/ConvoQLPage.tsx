"use client";

import { useState, useCallback } from "react";
import ChatThread from "./ChatThread";
import SQLPanel from "./SQLPanel";

interface QueryHistoryItem {
  id: string;
  question: string;
  sql: string;
  rows: number;
  time: number;
  timestamp: string;
  result?: any;
}

export default function ConvoQLPage() {
  const [messages, setMessages] = useState<any[]>([]);
  const [currentSql, setCurrentSql] = useState("");
  const [currentResult, setCurrentResult] = useState<any>(null);
  const [queryHistory, setQueryHistory] = useState<QueryHistoryItem[]>([]);

  const handleQueryExecuted = useCallback((sql: string, result: any, question: string) => {
    const newItem: QueryHistoryItem = {
      id: Date.now().toString(),
      question,
      sql,
      rows: result?.rows?.length || 0,
      time: result?.executionTime || 0,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      result,
    };
    setQueryHistory((prev) => [newItem, ...prev].slice(0, 50));
  }, []);

  return (
    <div className="flex h-screen w-full overflow-hidden" style={{ backgroundColor: "#080c10" }}>
      {/* Main Chat Area */}
      <ChatThread
        messages={messages}
        setMessages={setMessages}
        setCurrentSql={setCurrentSql}
        setCurrentResult={setCurrentResult}
        onQueryExecuted={handleQueryExecuted}
      />

      {/* SQL Inspector Panel */}
      <SQLPanel
        sql={currentSql}
        result={currentResult}
        executionTime={currentResult?.executionTime}
        history={queryHistory}
      />
    </div>
  );
}
