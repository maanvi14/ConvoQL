"use client";

import { useCallback, useState } from "react";
import { PanelLeft, PanelRight } from "lucide-react";
import SchemaExplorer from "@/components/SchemaExplorer";
import ChatThread from "@/components/ChatThread";
import SQLPanel from "@/components/SQLPanel";

interface QueryHistoryItem {
  id: string;
  question: string;
  sql: string;
  rows: number;
  time: number;
  timestamp: string;
  result?: any;
}

export default function ChatPage() {
  const [schema, setSchema] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [currentSql, setCurrentSql] = useState<string>("");
  const [currentResult, setCurrentResult] = useState<any>(null);
  const [queryHistory, setQueryHistory] = useState<QueryHistoryItem[]>([]);
  const [showSchema, setShowSchema] = useState(true);
  const [showSqlPanel, setShowSqlPanel] = useState(true);

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
    <div
      className="h-screen flex overflow-hidden relative"
      style={{ backgroundColor: "#080c10", color: "#e8edf2" }}
    >
      {showSchema && (
        <SchemaExplorer
          schema={schema}
          setSchema={setSchema}
          onClose={() => setShowSchema(false)}
        />
      )}

      {!showSchema && (
        <button
          onClick={() => setShowSchema(true)}
          className="absolute left-3 top-3 z-50 h-7 w-7 rounded-md flex items-center justify-center transition-all hover:opacity-90"
          style={{
            backgroundColor: "rgba(45,212,191,0.1)",
            border: "1px solid rgba(45,212,191,0.2)",
            color: "#2dd4bf",
          }}
          title="Show schema explorer"
          aria-label="Show schema explorer"
        >
          <PanelLeft className="w-3.5 h-3.5" />
        </button>
      )}

      <ChatThread 
        messages={messages} 
        setMessages={setMessages}
        setCurrentSql={setCurrentSql}
        setCurrentResult={setCurrentResult}
        onQueryExecuted={handleQueryExecuted}
      />

      {showSqlPanel && (
        <SQLPanel
          sql={currentSql}
          result={currentResult}
          executionTime={currentResult?.executionTime}
          history={queryHistory}
          onClose={() => setShowSqlPanel(false)}
        />
      )}

      {!showSqlPanel && (
        <button
          onClick={() => setShowSqlPanel(true)}
          className="absolute right-3 top-3 z-50 h-7 w-7 rounded-md flex items-center justify-center transition-all hover:opacity-90"
          style={{
            backgroundColor: "rgba(45,212,191,0.1)",
            border: "1px solid rgba(45,212,191,0.2)",
            color: "#2dd4bf",
          }}
          title="Show SQL inspector"
          aria-label="Show SQL inspector"
        >
          <PanelRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
