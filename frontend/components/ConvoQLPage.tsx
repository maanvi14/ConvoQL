"use client";

import { useState, useCallback } from "react";
import { PanelLeft, PanelRight } from "lucide-react";
import ChatThread from "./ChatThread";
import SQLPanel from "./SQLPanel";
import SchemaExplorer from "./SchemaExplorer";

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
  const [schema, setSchema] = useState<any>(null);

  // Toggle states for panels
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

  const handleCloseSchema = useCallback(() => {
    console.log("handleCloseSchema called");
    setShowSchema(false);
  }, []);

  const handleCloseSqlPanel = useCallback(() => {
    console.log("handleCloseSqlPanel called");
    setShowSqlPanel(false);
  }, []);

  console.log("ConvoQLPage render - showSchema:", showSchema, "showSqlPanel:", showSqlPanel);

  return (
    <div className="flex h-screen w-full overflow-hidden relative" style={{ backgroundColor: "#080c10" }}>
      {/* Schema Explorer - closable */}
      {showSchema && (
        <div className="w-60 flex-shrink-0" style={{ display: showSchema ? "block" : "none" }}>
          <SchemaExplorer 
            schema={schema} 
            setSchema={setSchema} 
            onClose={handleCloseSchema}
          />
        </div>
      )}

      {/* Floating re-open button for Schema (when closed) */}
      {!showSchema && (
        <button
          onClick={() => setShowSchema(true)}
          className="absolute left-3 top-3 z-50 h-7 w-7 rounded-md flex items-center justify-center transition-all hover:opacity-90"
          style={{
            backgroundColor: "rgba(45,212,191,0.1)",
            border: "1px solid rgba(45,212,191,0.2)",
            color: "#2dd4bf",
          }}
          title="Show schema"
        >
          <PanelLeft className="w-3.5 h-3.5" />
        </button>
      )}

      {/* Main Chat Area */}
      <ChatThread
        messages={messages}
        setMessages={setMessages}
        setCurrentSql={setCurrentSql}
        setCurrentResult={setCurrentResult}
        onQueryExecuted={handleQueryExecuted}
      />

      {/* SQL Inspector Panel - closable */}
      {showSqlPanel && (
        <div className="w-80 flex-shrink-0" style={{ display: showSqlPanel ? "block" : "none" }}>
          <SQLPanel
            sql={currentSql}
            result={currentResult}
            executionTime={currentResult?.executionTime}
            history={queryHistory}
            onClose={handleCloseSqlPanel}
          />
        </div>
      )}

      {/* Floating re-open button for SQL Panel (when closed) */}
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
        >
          <PanelRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
