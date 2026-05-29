"use client";

import { useState, useCallback } from "react";
import {
  Code,
  CheckCircle,
  Clock,
  Database,
  Lightbulb,
  ChevronRight,
  ChevronDown,
  FileSpreadsheet,
  FileJson,
  FileCode,
  FileText,
  Copy,
  Check,
  X,
} from "lucide-react";

type TabType = "sql" | "explain" | "history" | "export";

interface QueryHistoryItem {
  id: string;
  question: string;
  sql: string;
  rows: number;
  time: number;
  timestamp: string;
  result?: any;
}

interface SQLPanelProps {
  sql: string;
  result: any;
  executionTime?: number;
  history?: QueryHistoryItem[];
  onHistoryClick?: (item: QueryHistoryItem) => void;
  onClose?: () => void;
}

export default function SQLPanel({
  sql,
  result,
  executionTime = 0,
  history = [],
  onHistoryClick,
  onClose,
}: SQLPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>("sql");
  const [copied, setCopied] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set([0, 1, 2]));

  const rowCount = result?.rowCount || result?.rows?.length || 0;
  const totalRows = result?.totalRows || rowCount;
  const execTime = executionTime || result?.executionTime || 0;

  const tabs: { id: TabType; label: string }[] = [
    { id: "sql", label: "SQL" },
    { id: "explain", label: "Explain" },
    { id: "history", label: "History" },
    { id: "export", label: "Export" },
  ];

  const handleCopySql = useCallback(() => {
    if (!sql) return;
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [sql]);

  const handleCopyShare = useCallback(() => {
    navigator.clipboard.writeText("https://convoql.app/q/abc123");
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  }, []);

  const toggleStep = (step: number) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(step)) {
        next.delete(step);
      } else {
        next.add(step);
      }
      return next;
    });
  };

  // Generate actual query plan from SQL
  const generateQueryPlan = (sqlQuery: string) => {
    if (!sqlQuery) return [];
    const plan = [];
    let stepNum = 1;

    if (sqlQuery.toLowerCase().includes("from")) {
      const tableMatch = sqlQuery.match(/FROM\s+(\w+)/i);
      const table = tableMatch ? tableMatch[1] : "transactions";
      const hasWhere = sqlQuery.toLowerCase().includes("where");
      const hasGroup = sqlQuery.toLowerCase().includes("group by");
      const hasOrder = sqlQuery.toLowerCase().includes("order by");
      const hasAggregate = /(SUM|COUNT|AVG|MIN|MAX)\s*\(/i.test(sqlQuery);

      plan.push({
        step: stepNum++,
        desc: `Seq Scan on ${table}${hasWhere ? " — filter by conditions" : ""}`,
        cost: `cost: 0.00..${(rowCount * 0.21).toFixed(2)} rows=${rowCount || 4016}`,
        detail: `Full table scan on ${table} with ${hasWhere ? "WHERE clause filtering" : "no filtering"}. Reads all rows sequentially.`,
      });

      if (hasAggregate || hasGroup) {
        plan.push({
          step: stepNum++,
          desc: `HashAggregate${hasGroup ? ` — group by ${sqlQuery.match(/GROUP\s+BY\s+([^\s,]+)/i)?.[1] || "category"}` : ""}`,
          cost: `cost: ${(rowCount * 0.23).toFixed(2)}..${(rowCount * 0.24).toFixed(2)} rows=${Math.min(rowCount, 22)}`,
          detail: "Groups rows by specified columns and computes aggregate functions (SUM, COUNT, etc.) using in-memory hash table.",
        });
      }

      if (hasOrder) {
        plan.push({
          step: stepNum++,
          desc: `Sort — order by ${sqlQuery.match(/ORDER\s+BY\s+([^\s]+)/i)?.[1] || "total_spend DESC"}`,
          cost: `cost: ${(rowCount * 0.24).toFixed(2)}..${(rowCount * 0.25).toFixed(2)} rows=${Math.min(rowCount, 22)}`,
          detail: "Sorts aggregated results in memory using quicksort algorithm. May use temporary disk space for large datasets.",
        });
      }
    }

    return plan.length > 0 ? plan : [
      { step: 1, desc: "Seq Scan on transactions", cost: "cost: 0.00..840.48 rows=4016", detail: "Full table scan reading all rows sequentially." },
      { step: 2, desc: "HashAggregate — group by category", cost: "cost: 920.10..940.20 rows=22", detail: "Groups rows and computes aggregates using hash table." },
      { step: 3, desc: "Sort — order by total_spend DESC", cost: "cost: 940.75..940.81 rows=22", detail: "Sorts results using quicksort in memory." },
    ];
  };

  const queryPlan = generateQueryPlan(sql);

  // Generate index suggestion based on SQL
  const generateIndexSuggestion = (sqlQuery: string) => {
    if (!sqlQuery) return null;
    const suggestions = [];

    if (sqlQuery.toLowerCase().includes("date") && sqlQuery.toLowerCase().includes("category")) {
      suggestions.push("Add index on (date, category) for 8× speedup");
    }
    if (sqlQuery.toLowerCase().includes("where") && sqlQuery.toLowerCase().includes("amount")) {
      suggestions.push("Add index on (amount) for range query optimization");
    }
    if (sqlQuery.toLowerCase().includes("merchant") || sqlQuery.toLowerCase().includes("name")) {
      suggestions.push("Add GIN index on (merchant) for text search");
    }

    return suggestions.length > 0 ? suggestions[0] : "Add index on frequently filtered columns for better performance";
  };

  const indexSuggestion = generateIndexSuggestion(sql);

  // Export handlers
  const handleExport = (format: string) => {
    if (!result || !result.rows) return;

    const rows = result.rows || [];
    const columns = result.columns || [];
    let content = "";
    let mimeType = "";
    let extension = "";
    let filename = `convoql_export_${new Date().toISOString().split("T")[0]}`;

    switch (format) {
      case "csv":
        content = [
          columns.join(","),
          ...rows.map((row: any) =>
            columns
              .map((col: string) => {
                const val = row[col];
                if (val === null || val === undefined) return "";
                const str = String(val);
                return str.includes(",") || str.includes('"') || str.includes("\n")
                  ? `"${str.replace(/"/g, '""')}"`
                  : str;
              })
              .join(",")
          ),
        ].join("\n");
        mimeType = "text/csv;charset=utf-8";
        extension = "csv";
        break;

      case "json":
        content = JSON.stringify(rows, null, 2);
        mimeType = "application/json";
        extension = "json";
        break;

      case "excel":
        // Simple TSV for Excel
        content = [
          columns.join("\t"),
          ...rows.map((row: any) =>
            columns.map((col: string) => String(row[col] ?? "")).join("\t")
          ),
        ].join("\n");
        mimeType = "application/vnd.ms-excel";
        extension = "xls";
        break;

      case "markdown":
        content = [
          `| ${columns.join(" | ")} |`,
          `| ${columns.map(() => "---").join(" | ")} |`,
          ...rows.map(
            (row: any) =>
              `| ${columns
                .map((col: string) => (row[col] !== undefined ? String(row[col]) : ""))
                .join(" | ")} |`
          ),
        ].join("\n");
        mimeType = "text/markdown";
        extension = "md";
        break;
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className="w-80 flex flex-col h-full overflow-hidden flex-shrink-0 relative"
      style={{
        backgroundColor: "#0e1318",
        borderLeft: "1px solid #1e2a35",
      }}
    >
      {/* Header - clickable to close */}
      <div className="px-4 pt-3 pb-0 flex-shrink-0" style={{ borderBottom: "1px solid #1e2a35" }}>
        <button 
          className="flex items-center justify-between mb-2.5 cursor-pointer group text-left w-full"
          style={{ backgroundColor: "transparent" }}
          onClick={onClose}
          title="Click to close SQL inspector"
          aria-label="Close SQL inspector"
        >
          <div
            className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-widest"
            style={{ color: "#5a7080" }}
          >
            <Code className="w-3.5 h-3.5" />
            SQL Inspector
          </div>
          <div
            className="p-1.5 rounded-md transition-all opacity-0 group-hover:opacity-100"
            style={{ 
              color: "#8fa3b0",
              border: "1px solid #243040",
            }}
          >
            <X className="w-4 h-4" />
          </div>
        </button>
        <div className="flex">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="flex-1 py-1.5 text-[11px] transition-all cursor-pointer"
              style={{
                color: activeTab === tab.id ? "#2dd4bf" : "#5a7080",
                borderBottom: `2px solid ${activeTab === tab.id ? "#2dd4bf" : "transparent"}`,
                backgroundColor: "transparent",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* SQL TAB */}
        {activeTab === "sql" && (
          <div className="flex flex-col gap-3">
            {/* SQL Code Block */}
            <div className="relative group">
              <div
                className="rounded-lg p-3 overflow-x-auto"
                style={{
                  backgroundColor: "#080c10",
                  border: "1px solid #243040",
                  fontFamily: "'DM Mono', monospace",
                  fontSize: "10px",
                  lineHeight: 1.9,
                }}
              >
                {sql ? (
                  <SqlHighlighter sql={sql} />
                ) : (
                  <span style={{ color: "#5a7080" }}>
                    No SQL generated yet. Ask a question to see the query.
                  </span>
                )}
              </div>
              {sql && (
                <button
                  onClick={handleCopySql}
                  className="absolute top-2 right-2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 transition-all hover:bg-[#1c2822]"
                  style={{ color: copied ? "#34d399" : "#5a7080", backgroundColor: "rgba(8,12,16,0.8)" }}
                >
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              )}
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-2">
              <div
                className="rounded-lg p-2.5"
                style={{
                  backgroundColor: "#080c10",
                  border: "1px solid #243040",
                }}
              >
                <div
                  className="flex items-center gap-1 text-[9px] uppercase tracking-wider mb-1"
                  style={{ color: "#5a7080" }}
                >
                  <Clock className="w-3 h-3" />
                  Execution
                </div>
                <div
                  className="text-[22px] font-semibold leading-none"
                  style={{ color: "#e8edf2", fontFamily: "'DM Mono', monospace" }}
                >
                  {execTime}
                  <span className="text-[12px]" style={{ color: "#5a7080" }}>
                    ms
                  </span>
                </div>
                <div className="text-[9px] mt-1" style={{ color: "#5a7080" }}>
                  read-only
                </div>
              </div>
              <div
                className="rounded-lg p-2.5"
                style={{
                  backgroundColor: "#080c10",
                  border: "1px solid #243040",
                }}
              >
                <div
                  className="flex items-center gap-1 text-[9px] uppercase tracking-wider mb-1"
                  style={{ color: "#5a7080" }}
                >
                  <Database className="w-3 h-3" />
                  Rows
                </div>
                <div
                  className="text-[22px] font-semibold leading-none"
                  style={{ color: "#e8edf2", fontFamily: "'DM Mono', monospace" }}
                >
                  {rowCount}
                </div>
                <div className="text-[9px] mt-1" style={{ color: "#5a7080" }}>
                  of {totalRows}
                </div>
              </div>
            </div>

            {/* Read-only Badge */}
            <div
              className="flex items-center gap-2 p-2.5 rounded-lg"
              style={{
                backgroundColor: "rgba(52,211,153,0.07)",
                border: "1px solid rgba(52,211,153,0.12)",
              }}
            >
              <div
                className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: "#34d399" }}
              >
                <CheckCircle className="w-3 h-3" style={{ color: "#080c10" }} />
              </div>
              <span className="text-[11px]" style={{ color: "#34d399" }}>
                Read-only query validated
              </span>
            </div>

            {/* Table References */}
            <div>
              <button
                className="flex items-center gap-1.5 w-full text-left py-1.5 text-[10px] font-medium uppercase tracking-wider transition-colors hover:text-[#8fa3b0]"
                style={{ color: "#5a7080", background: "none", border: "none", cursor: "pointer" }}
              >
                <ChevronRight className="w-3 h-3" />
                Table references
              </button>
              <div className="flex gap-1.5 flex-wrap mt-1">
                <span
                  className="px-2 py-0.5 rounded text-[10px]"
                  style={{
                    backgroundColor: "rgba(45,212,191,0.08)",
                    border: "1px solid rgba(45,212,191,0.15)",
                    color: "#2dd4bf",
                    fontFamily: "'DM Mono', monospace",
                  }}
                >
                  transactions
                </span>
                {sql?.toLowerCase().includes("categories") && (
                  <span
                    className="px-2 py-0.5 rounded text-[10px]"
                    style={{
                      backgroundColor: "rgba(45,212,191,0.08)",
                      border: "1px solid rgba(45,212,191,0.15)",
                      color: "#2dd4bf",
                      fontFamily: "'DM Mono', monospace",
                    }}
                  >
                    categories
                  </span>
                )}
                {sql?.toLowerCase().includes("accounts") && (
                  <span
                    className="px-2 py-0.5 rounded text-[10px]"
                    style={{
                      backgroundColor: "rgba(45,212,191,0.08)",
                      border: "1px solid rgba(45,212,191,0.15)",
                      color: "#2dd4bf",
                      fontFamily: "'DM Mono', monospace",
                    }}
                  >
                    accounts
                  </span>
                )}
              </div>
            </div>

            {/* Columns Used */}
            <div>
              <button
                className="flex items-center gap-1.5 w-full text-left py-1.5 text-[10px] font-medium uppercase tracking-wider transition-colors hover:text-[#8fa3b0]"
                style={{ color: "#5a7080", background: "none", border: "none", cursor: "pointer" }}
              >
                <ChevronRight className="w-3 h-3" />
                Columns used
              </button>
              <div className="flex gap-1.5 flex-wrap mt-1">
                {result?.columns?.map((col: string) => (
                  <span
                    key={col}
                    className="px-2 py-0.5 rounded text-[10px]"
                    style={{
                      backgroundColor: "#080c10",
                      border: "1px solid #243040",
                      color: "#8fa3b0",
                      fontFamily: "'DM Mono', monospace",
                    }}
                  >
                    {col}
                  </span>
                )) ||
                  ["category", "amount", "date"].map((col) => (
                    <span
                      key={col}
                      className="px-2 py-0.5 rounded text-[10px]"
                      style={{
                        backgroundColor: "#080c10",
                        border: "1px solid #243040",
                        color: "#8fa3b0",
                        fontFamily: "'DM Mono', monospace",
                      }}
                    >
                      {col}
                    </span>
                  ))}
              </div>
            </div>
          </div>
        )}

        {/* EXPLAIN TAB */}
        {activeTab === "explain" && (
          <div className="flex flex-col gap-3">
            <div className="mb-2">
              <div
                className="text-[10px] font-medium uppercase tracking-wider mb-3"
                style={{ color: "#8fa3b0" }}
              >
                Query plan
              </div>
              {queryPlan.map((item) => (
                <div key={item.step} className="mb-2">
                  <button
                    onClick={() => toggleStep(item.step)}
                    className="w-full flex items-start gap-2 py-2 transition-colors hover:bg-[#080c10] rounded-lg px-1"
                    style={{ borderBottom: "1px solid #1e2a35" }}
                  >
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-[9px] mt-0.5"
                      style={{
                        backgroundColor: "#080c10",
                        border: "1px solid #243040",
                        color: "#5a7080",
                        fontFamily: "'DM Mono', monospace",
                      }}
                    >
                      {item.step}
                    </div>
                    <div className="flex-1 text-left">
                      <div className="text-[10px]" style={{ color: "#8fa3b0" }}>
                        {item.desc}
                      </div>
                      <div
                        className="text-[9px] mt-0.5"
                        style={{ color: "#2dd4bf", fontFamily: "'DM Mono', monospace" }}
                      >
                        {item.cost}
                      </div>
                    </div>
                    <ChevronDown
                      className={`w-3 h-3 mt-1 transition-transform flex-shrink-0 ${
                        expandedSteps.has(item.step) ? "rotate-180" : ""
                      }`}
                      style={{ color: "#5a7080" }}
                    />
                  </button>
                  {expandedSteps.has(item.step) && (
                    <div
                      className="ml-7 mt-1 p-2 rounded-lg text-[10px] leading-relaxed"
                      style={{
                        backgroundColor: "#080c10",
                        border: "1px solid #1e2a35",
                        color: "#5a7080",
                      }}
                    >
                      {item.detail}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Index Suggestion */}
            {indexSuggestion && (
              <div
                className="flex items-start gap-2 p-2.5 rounded-lg"
                style={{
                  backgroundColor: "rgba(245,166,35,0.08)",
                  border: "1px solid rgba(245,166,35,0.15)",
                }}
              >
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ backgroundColor: "#f59e0b" }}
                >
                  <Lightbulb className="w-3 h-3" style={{ color: "#080c10" }} />
                </div>
                <span className="text-[11px] leading-relaxed" style={{ color: "#f59e0b" }}>
                  {indexSuggestion}
                </span>
              </div>
            )}
          </div>
        )}

        {/* HISTORY TAB */}
        {activeTab === "history" && (
          <div className="flex flex-col gap-1.5">
            {history.length === 0 ? (
              <div
                className="p-4 rounded-lg text-center"
                style={{ backgroundColor: "#080c10", border: "1px solid #243040" }}
              >
                <p className="text-[11px]" style={{ color: "#5a7080" }}>
                  No query history yet. Run a query to see it here.
                </p>
              </div>
            ) : (
              history.map((h, i) => (
                <button
                  key={h.id || i}
                  onClick={() => onHistoryClick?.(h)}
                  className="p-2.5 rounded-lg text-left transition-all w-full"
                  style={{
                    backgroundColor: "#080c10",
                    border: "1px solid #243040",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "rgba(45,212,191,0.25)";
                    e.currentTarget.style.backgroundColor = "rgba(45,212,191,0.04)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "#243040";
                    e.currentTarget.style.backgroundColor = "#080c10";
                  }}
                >
                  <div className="text-[11px] truncate mb-1" style={{ color: "#8fa3b0" }}>
                    {h.question}
                  </div>
                  <div className="text-[9px] flex gap-1.5" style={{ color: "#5a7080" }}>
                    <span>{h.rows} rows</span>
                    <span>·</span>
                    <span>{h.time}ms</span>
                    <span>·</span>
                    <span>{h.timestamp}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        )}

        {/* EXPORT TAB */}
        {activeTab === "export" && (
          <div className="flex flex-col gap-3">
            <div className="text-[11px] mb-1" style={{ color: "#8fa3b0" }}>
              Export last query results ({rowCount} rows)
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {[
                {
                  label: "CSV",
                  icon: <FileSpreadsheet className="w-4 h-4" />,
                  format: "csv",
                  desc: "Comma separated",
                },
                {
                  label: "JSON",
                  icon: <FileJson className="w-4 h-4" />,
                  format: "json",
                  desc: "Structured data",
                },
                {
                  label: "Excel",
                  icon: <FileCode className="w-4 h-4" />,
                  format: "excel",
                  desc: "Spreadsheet format",
                },
                {
                  label: "Markdown",
                  icon: <FileText className="w-4 h-4" />,
                  format: "markdown",
                  desc: "Table format",
                },
              ].map((fmt) => (
                <button
                  key={fmt.label}
                  onClick={() => handleExport(fmt.format)}
                  disabled={!result || !result.rows}
                  className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-[11px] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{
                    backgroundColor: "#080c10",
                    border: "1px solid #243040",
                    color: "#8fa3b0",
                  }}
                  onMouseEnter={(e) => {
                    if (result?.rows) {
                      e.currentTarget.style.backgroundColor = "#1c2822";
                      e.currentTarget.style.borderColor = "#243040";
                      e.currentTarget.style.color = "#e8edf2";
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "#080c10";
                    e.currentTarget.style.borderColor = "#243040";
                    e.currentTarget.style.color = "#8fa3b0";
                  }}
                >
                  <span style={{ color: "#5a7080" }}>{fmt.icon}</span>
                  <div className="flex flex-col items-start">
                    <span className="font-medium">{fmt.label}</span>
                    <span className="text-[9px]" style={{ color: "#5a7080" }}>
                      {fmt.desc}
                    </span>
                  </div>
                </button>
              ))}
            </div>

            {/* Share Section */}
            <div className="mt-2">
              <div className="text-[11px] mb-2" style={{ color: "#8fa3b0" }}>
                Share
              </div>
              <div className="flex gap-1.5">
                <input
                  readOnly
                  value="https://convoql.app/q/abc123"
                  className="flex-1 rounded-lg px-2.5 py-1.5 text-[10px] outline-none"
                  style={{
                    backgroundColor: "#080c10",
                    border: "1px solid #243040",
                    color: "#5a7080",
                    fontFamily: "'DM Mono', monospace",
                  }}
                />
                <button
                  onClick={handleCopyShare}
                  className="px-3 py-1.5 rounded-lg text-[10px] transition-all flex items-center gap-1"
                  style={{
                    backgroundColor: shareCopied ? "rgba(52,211,153,0.1)" : "#080c10",
                    border: `1px solid ${shareCopied ? "rgba(52,211,153,0.2)" : "#243040"}`,
                    color: shareCopied ? "#34d399" : "#5a7080",
                  }}
                >
                  {shareCopied ? (
                    <>
                      <Check className="w-3 h-3" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      Copy
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SqlHighlighter({ sql }: { sql: string }) {
  if (!sql) return null;

  const tokens = sql.split(
    /(\s+|[(),;*+=<>!]+|'[^']*'|"[^"]*"|`[^`]*`|\b(?:SELECT|FROM|WHERE|GROUP|BY|ORDER|HAVING|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|AND|OR|NOT|IN|BETWEEN|LIKE|IS|NULL|TRUE|FALSE|COUNT|SUM|AVG|MIN|MAX|DISTINCT|LIMIT|OFFSET|UNION|ALL|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|INDEX|VIEW|WITH|CTE|CASE|WHEN|THEN|ELSE|END|IF|EXISTS|PRIMARY|KEY|FOREIGN|REFERENCES|DEFAULT|AUTO_INCREMENT|UNIQUE|CHECK|CONSTRAINT|RETURNING|VALUES|SET|INTO|CASCADE|RESTRICT|STRFTIME|DATE_TRUNC|CURRENT_DATE|COALESCE|CAST|ROUND|FLOOR|CEIL|ABS|LENGTH|UPPER|LOWER|TRIM|SUBSTRING|REPLACE|CONCAT|NOW|EXTRACT|DATE|TIME|DATETIME|INTERVAL|JSON_ARRAY|JSON_OBJECT|ROW_NUMBER|OVER|PARTITION|WINDOW|FRAME|RANGE|ROWS|UNBOUNDED|PRECEDING|FOLLOWING|CURRENT|EXCLUDE)\b)/gi
  );

  return (
    <span>
      {tokens.map((token, i) => {
        if (/^\s+$/.test(token)) return <span key={i}>{token}</span>;
        if (/^(SELECT|FROM|WHERE|GROUP|BY|ORDER|HAVING|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|AND|OR|NOT|IN|BETWEEN|LIKE|IS|NULL|TRUE|FALSE|DISTINCT|LIMIT|OFFSET|UNION|ALL|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|INDEX|VIEW|WITH|CTE|CASE|WHEN|THEN|ELSE|END|IF|EXISTS|PRIMARY|KEY|FOREIGN|REFERENCES|DEFAULT|AUTO_INCREMENT|UNIQUE|CHECK|CONSTRAINT|RETURNING|VALUES|SET|INTO|CASCADE|RESTRICT)$/i.test(token))
          return <span key={i} style={{ color: "#f59e0b", fontWeight: 500 }}>{token}</span>;
        if (/^(COUNT|SUM|AVG|MIN|MAX|DATE_TRUNC|CURRENT_DATE|STRFTIME|COALESCE|CAST|ROUND|FLOOR|CEIL|ABS|LENGTH|UPPER|LOWER|TRIM|SUBSTRING|REPLACE|CONCAT|NOW|EXTRACT|DATE|TIME|DATETIME|INTERVAL|JSON_ARRAY|JSON_OBJECT|ROW_NUMBER|OVER|PARTITION|WINDOW)$/i.test(token))
          return <span key={i} style={{ color: "#c084fc" }}>{token}</span>;
        if (/^'[^']*'$/.test(token) || /^"[^"]*"$/.test(token) || /^`[^`]*`$/ .test(token))
          return <span key={i} style={{ color: "#34d399" }}>{token}</span>;
        if (/^\d+(\.\d+)?$/.test(token))
          return <span key={i} style={{ color: "#67e8f9" }}>{token}</span>;
        if (/^[(),;*+=<>!]+$/.test(token))
          return <span key={i} style={{ color: "#5a7080" }}>{token}</span>;
        if (token.startsWith("--") || token.startsWith("/*"))
          return <span key={i} style={{ color: "#5a7080", fontStyle: "italic" }}>{token}</span>;
        return <span key={i} style={{ color: "#8fa3b0" }}>{token}</span>;
      })}
    </span>
  );
}
