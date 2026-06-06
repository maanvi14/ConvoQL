"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Sparkles, BarChart3, LineChart, PieChart, Table, ChevronRight, Plus } from "lucide-react";
import { querySync, createSession } from "@/lib/api";
import AutoChart from "./AutoChart";

type ChartType = "bar" | "line" | "pie" | "table";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sql?: string;
  hasChart?: boolean;
  chartType?: ChartType;
  chartTitle?: string;
  hasTable?: boolean;
  result?: {
    columns: string[];
    rows: Record<string, any>[];
    executionTime?: number;
    rowCount?: number;
  };
  insight?: string;
  executionTime?: number;
  timestamp?: string;
}

interface ChatThreadProps {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setCurrentSql: React.Dispatch<React.SetStateAction<string>>;
  setCurrentResult: React.Dispatch<React.SetStateAction<any>>;
  onQueryExecuted?: (sql: string, result: any, question: string) => void;
}

export default function ChatThread({
  messages,
  setMessages,
  setCurrentSql,
  setCurrentResult,
  onQueryExecuted,
}: ChatThreadProps) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      const session = await createSession();
      const startTime = performance.now();
      const data = await querySync(input, session.session_id);
      const endTime = performance.now();
      const execTime = Math.round(endTime - startTime);

      // Ensure result has proper structure
      const resultData = data.result || {
        columns: data.columns || [],
        rows: data.rows || [],
        executionTime: data.execution_time_ms || execTime,
        rowCount: data.row_count || (data.rows?.length || 0),
      };

      // === CRITICAL FIX: Auto-detect chart type from result data ===
      const detectedChartType = detectChartType(resultData, input);
      const shouldShowChart = detectedChartType !== "table" && resultData.rows && resultData.rows.length > 0;

      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.answer || data.explanation || "Here's what I found:",
        sql: data.sql || data.generated_sql,
        hasChart: data.has_chart || data.chart_type || shouldShowChart,
        chartType: (data.chart_type || data.chartType || detectedChartType) as ChartType,
        chartTitle: data.chart_title || data.chartTitle || input,
        hasTable: data.has_table || (resultData.rows?.length > 0 && resultData.rows?.length <= 50),
        result: resultData,
        insight: data.insight,
        executionTime: data.execution_time_ms || execTime,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setCurrentSql(data.sql || data.generated_sql || "");
      setCurrentResult(resultData);

      // Notify parent for history tracking
      if (onQueryExecuted && (data.sql || data.generated_sql)) {
        onQueryExecuted(
          data.sql || data.generated_sql,
          resultData,
          input
        );
      }
    } catch (e: any) {
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Something went wrong: ${e.message || "Failed to process query"}. Try rephrasing your question.`,
        hasChart: false,
        hasTable: false,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  // === CRITICAL FIX: Auto-detect chart type from data shape ===
  function detectChartType(result: any, question: string): ChartType {
    if (!result || !result.rows || result.rows.length === 0) return "table";

    const rows = result.rows;
    const columns = result.columns || [];
    const q = question.toLowerCase();

    // Find numeric columns
    const numericCols = columns.filter((c: string) => {
      const val = rows[0]?.[c];
      return typeof val === "number" || (typeof val === "string" && !isNaN(Number(val)) && val !== "");
    });

    // Find date columns
    const dateCol = columns.find((c: string) => {
      const val = rows[0]?.[c];
      if (typeof val !== "string") return false;
      const cl = c.toLowerCase();
      return cl.includes("date") || cl.includes("month") || cl.includes("year") || !isNaN(new Date(val).getTime());
    });

    // Find label columns (non-numeric, non-date)
    const labelCols = columns.filter((c: string) => !numericCols.includes(c) && c !== dateCol);

    // Time series -> line chart
    if (dateCol && numericCols.length > 0 && rows.length >= 3) {
      return "line";
    }

    // Few categories with values -> pie chart
    if (labelCols.length > 0 && numericCols.length > 0 && rows.length <= 6) {
      return "pie";
    }

    // Multiple categories with values -> bar chart
    if (labelCols.length > 0 && numericCols.length > 0) {
      return "bar";
    }

    // Budget comparison queries -> bar chart
    if (q.includes("budget") && numericCols.length >= 2) {
      return "bar";
    }

    return "table";
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleChipClick = (text: string) => {
    setInput(text);
    textareaRef.current?.focus();
  };

  const QUICK_CHIPS = [
    "Compare my budget VS actual spending for May",
    "Show me top 3 Categories by spending",
    "Show all transactions from 'Uber'",
    "Which category has the highest spending?",
    "Show me total spending by payment method",
    "Account Balances",
  ];

  return (
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden" style={{ backgroundColor: "#080c10" }}>
      {/* Topbar */}
      <div
        className="h-11 flex items-center px-4 gap-2 flex-shrink-0"
        style={{ backgroundColor: "#0e1318", borderBottom: "1px solid #1e2a35" }}
      >
        <div className="flex items-center gap-1.5 text-[12px]">
          <span style={{ color: "#5a7080" }}>my_finance_db</span>
          <span style={{ color: "#5a7080" }}>/</span>
          <span style={{ color: "#e8edf2", fontFamily: "'DM Mono', monospace" }}>transactions</span>
        </div>
        <div className="w-px h-5 mx-2" style={{ backgroundColor: "#1e2a35" }} />
        <div className="flex gap-0.5">
          <button
            className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] transition-all"
            style={{
              color: "#e8edf2",
              backgroundColor: "#1c2822",
            }}
          >
            Chat
          </button>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <button
            className="h-7 px-3 rounded-md text-[11px] font-medium flex items-center gap-1.5 transition-all hover:opacity-90"
            style={{ backgroundColor: "#2dd4bf", color: "#080c10" }}
            onClick={() => setMessages([])}
          >
            <Plus className="w-3.5 h-3.5" />
            New chat
          </button>
        </div>
      </div>

      {/* Chat Body */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        <div className="max-w-[800px] mx-auto flex flex-col gap-5">

          {/* Welcome Card */}
          {messages.length === 0 && (
            <div
              className="rounded-xl p-5 flex gap-3.5"
              style={{ backgroundColor: "#141b22", border: "1px solid #243040" }}
            >
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: "#2dd4bf" }}
              >
                <span className="text-[12px] font-semibold" style={{ color: "#080c10" }}>CQ</span>
              </div>
              <div>
                <div className="text-[14px] font-medium mb-1" style={{ color: "#e8edf2" }}>
                  ConvoQL is ready
                </div>
                <div className="text-[12px] leading-relaxed" style={{ color: "#8fa3b0" }}>
                  Ask me anything about your{" "}
                  <strong style={{ color: "#2dd4bf" }}>transactions</strong>. I can analyze
                  spending, detect anomalies, and show you charts — all in plain English.
                </div>
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((msg, index) => (
            <div
              key={msg.id}
              className={msg.role === "user" ? "flex flex-row-reverse gap-2.5" : "flex gap-2.5"}
            >
              {/* Avatar */}
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-medium flex-shrink-0 mt-0.5"
                style={{
                  backgroundColor:
                    msg.role === "user" ? "#141b22" : "rgba(45,212,191,0.1)",
                  border: `1px solid ${msg.role === "user" ? "#1e2a35" : "rgba(45,212,191,0.2)"}`,
                  color: msg.role === "user" ? "#8fa3b0" : "#2dd4bf",
                  fontFamily: "'DM Mono', monospace",
                }}
              >
                {msg.role === "user" ? "U" : "AI"}
              </div>

              {/* Content */}
              <div className="max-w-[88%] flex flex-col gap-2">
                {/* Meta */}
                <div className="text-[10px] flex items-center gap-1.5" style={{ color: "#5a7080" }}>
                  {msg.role === "assistant" && (
                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#2dd4bf" }} />
                  )}
                  <span>{msg.role === "user" ? "You" : "ConvoQL"}</span>
                  <span>·</span>
                  <span>{msg.executionTime ? `${msg.executionTime}ms` : msg.timestamp || "just now"}</span>
                </div>

                {/* Bubble */}
                <div
                  className="px-3.5 py-2.5 rounded-[10px] text-[12px] leading-relaxed"
                  style={{
                    backgroundColor:
                      msg.role === "user" ? "rgba(45,212,191,0.08)" : "#141b22",
                    border: `1px solid ${msg.role === "user" ? "rgba(45,212,191,0.12)" : "#243040"}`,
                    color: "#e8edf2",
                  }}
                >
                  {msg.content}
                  {msg.insight && (
                    <div className="mt-1.5 text-[11px] flex items-center gap-1" style={{ color: "#f59e0b" }}>
                      <span>💡</span>
                      <span>{msg.insight}</span>
                    </div>
                  )}
                </div>

                {/* Chart - Only show if hasChart is true and result exists */}
                {msg.hasChart && msg.result && msg.chartType && msg.chartType !== "table" && (
                  <div className="mt-1">
                    <AutoChart
                      data={msg.result}
                      chartType={msg.chartType}
                      title={msg.chartTitle || "Chart"}
                    />
                  </div>
                )}

                {/* Table - Show if hasTable is true */}
                {msg.hasTable && msg.result && msg.result.rows && msg.result.rows.length > 0 && (
                  <div
                    className="mt-1 rounded-lg overflow-hidden"
                    style={{ border: "1px solid #243040" }}
                  >
                    <div className="overflow-x-auto">
                      <table className="w-full text-[11px]">
                        <thead>
                          <tr
                            style={{
                              borderBottom: "1px solid #243040",
                              backgroundColor: "#0e1318",
                            }}
                          >
                            {msg.result.columns?.map((col: string) => (
                              <th
                                key={col}
                                className="text-left py-2 px-3 font-medium uppercase tracking-wider"
                                style={{ color: "#5a7080", fontSize: "9px" }}
                              >
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {msg.result.rows?.map((row: any, i: number) => (
                            <tr
                              key={i}
                              style={{ borderBottom: "1px solid #1e2a35" }}
                              className="hover:bg-[#1c2822] transition-colors"
                            >
                              {msg.result.columns?.map((col: string) => (
                                <td
                                  key={col}
                                  className="py-2 px-3"
                                  style={{
                                    color:
                                      col === "amount" ||
                                      col === "total" ||
                                      col === "total_spend" ||
                                      col === "sum" ||
                                      col === "avg" ||
                                      col === "count"
                                        ? "#2dd4bf"
                                        : "#8fa3b0",
                                    fontFamily: "'DM Mono', monospace",
                                    fontSize: "11px",
                                  }}
                                >
                                  {typeof row[col] === "number"
                                    ? `₹${row[col]!.toLocaleString()}`
                                    : String(row[col] ?? "-")}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Typing Indicator */}
          {loading && (
            <div className="flex gap-2.5 items-center">
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
                style={{
                  backgroundColor: "rgba(45,212,191,0.1)",
                  border: "1px solid rgba(45,212,191,0.2)",
                }}
              >
                <span className="text-[10px]" style={{ color: "#2dd4bf" }}>
                  AI
                </span>
              </div>
              <div
                className="flex items-center gap-1 px-4 py-3 rounded-[10px]"
                style={{
                  backgroundColor: "#141b22",
                  border: "1px solid #243040",
                }}
              >
                <div
                  className="w-1.5 h-1.5 rounded-full animate-bounce"
                  style={{ backgroundColor: "#5a7080", animationDelay: "0ms" }}
                />
                <div
                  className="w-1.5 h-1.5 rounded-full animate-bounce"
                  style={{ backgroundColor: "#5a7080", animationDelay: "150ms" }}
                />
                <div
                  className="w-1.5 h-1.5 rounded-full animate-bounce"
                  style={{ backgroundColor: "#5a7080", animationDelay: "300ms" }}
                />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Zone */}
      <div className="px-5 pb-4 pt-3 flex-shrink-0 max-w-[800px] mx-auto w-full">
        <div className="flex gap-1.5 mb-2.5 flex-wrap">
          {QUICK_CHIPS.map((chip) => (
            <button
              key={chip}
              onClick={() => handleChipClick(chip)}
              className="px-3 py-1 rounded-full text-[10px] transition-all flex items-center gap-1"
              style={{
                border: "1px solid #243040",
                color: "#5a7080",
                backgroundColor: "transparent",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "rgba(45,212,191,0.25)";
                e.currentTarget.style.color = "#2dd4bf";
                e.currentTarget.style.backgroundColor = "rgba(45,212,191,0.04)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "#243040";
                e.currentTarget.style.color = "#5a7080";
                e.currentTarget.style.backgroundColor = "transparent";
              }}
            >
              <ChevronRight className="w-3 h-3" />
              {chip}
            </button>
          ))}
        </div>

        <div className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
            }}
            onKeyDown={handleKeyDown}
            placeholder={loading ? "Processing..." : "Ask about your income, spending, accounts..."}
            disabled={loading}
            rows={1}
            className="flex-1 rounded-lg px-3.5 py-2.5 text-[13px] outline-none resize-none transition-colors"
            style={{
              backgroundColor: "#141b22",
              border: "1px solid #243040",
              color: "#e8edf2",
              minHeight: "44px",
              maxHeight: "120px",
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(45,212,191,0.3)")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "#243040")}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="w-11 h-11 rounded-lg flex items-center justify-center transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: "#2dd4bf", color: "#080c10" }}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-2 mt-2">
          <span className="text-[10px]" style={{ color: "#5a7080" }}>
            Press{" "}
            <kbd
              className="px-1 py-px rounded text-[9px]"
              style={{
                backgroundColor: "#141b22",
                border: "1px solid #243040",
                fontFamily: "'DM Mono', monospace",
              }}
            >
              Enter
            </kbd>{" "}
            to send
          </span>
        </div>
      </div>
    </div>
  );
}
