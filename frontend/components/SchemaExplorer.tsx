"use client";

import { useState, useEffect } from "react";
import { Search, ChevronDown, ChevronRight, X } from "lucide-react";
import { getSchema } from "@/lib/api";

interface TableInfo {
  name: string;
  count: number;
  columns: {
    name: string;
    type: string;
    typeColor: string;
    example?: string;
  }[];
}

const SUGGESTIONS = [
  "Highest expense last month",
  "Spending by category",
  "Average daily spend",
];

interface SchemaExplorerProps {
  schema: any;
  setSchema: any;
  onClose?: () => void;
}

export default function SchemaExplorer({ schema, setSchema, onClose }: SchemaExplorerProps) {
  const [expandedTables, setExpandedTables] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTable, setActiveTable] = useState<string>("");

  useEffect(() => {
    getSchema().then(data => {
      setSchema(data);
      if (data.tables?.length > 0) {
        setExpandedTables([data.tables[0].name]);
        setActiveTable(data.tables[0].name);
      }
    }).catch(console.error);
  }, [setSchema]);

  const toggleTable = (name: string) => {
    setExpandedTables((prev) =>
      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]
    );
    setActiveTable(name);
  };

  const tables: TableInfo[] = schema?.tables?.map((t: any) => ({
    name: t.name,
    count: t.row_count || 0,
    columns: t.columns.map((c: any) => ({
      name: c.name,
      type: c.type?.substring(0, 3).toUpperCase() || "UNK",
      typeColor: getTypeColor(c.type),
      example: c.example,
    })),
  })) || [];

  const filteredTables = tables.filter((t) =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.columns.some((c) => c.name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div
      className="w-60 flex flex-col h-full overflow-hidden flex-shrink-0 relative"
      style={{
        backgroundColor: "#0e1318",
        borderRight: "1px solid #1e2a35",
      }}
    >
      {/* Brand - clickable to close */}
      <button
        className="p-3.5 flex items-center gap-2.5 flex-shrink-0 cursor-pointer group text-left w-full"
        style={{ 
          borderBottom: "1px solid #1e2a35",
          backgroundColor: "transparent",
        }}
        onClick={onClose}
        title="Click to close schema"
        aria-label="Close schema explorer"
      >
        <div
          className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: "#2dd4bf" }}
        >
          <span
            className="text-[10px] font-medium"
            style={{ color: "#080c10", fontFamily: "'DM Mono', monospace" }}
          >
            CQ
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium" style={{ color: "#e8edf2" }}>
            ConvoQL
          </div>
          <div className="text-[9px] tracking-wider uppercase" style={{ color: "#5a7080" }}>
            Conversational Analytics
          </div>
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

      {/* Connection Badge */}
      <div
        className="mx-3 mt-3 p-2 rounded-md flex items-center gap-2 flex-shrink-0"
        style={{
          backgroundColor: "rgba(45,212,191,0.04)",
          border: "1px solid rgba(45,212,191,0.15)",
        }}
      >
        <div
          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{
            backgroundColor: "#2dd4bf",
            boxShadow: "0 0 6px rgba(45,212,191,0.5)",
          }}
        />
        <div className="min-w-0">
          <div
            className="text-[11px] font-medium truncate"
            style={{ color: "#2dd4bf", fontFamily: "'DM Mono', monospace" }}
          >
            {schema?.dialect || "sqlite"}_db
          </div>
          <div className="text-[9px] uppercase tracking-wider" style={{ color: "#5a7080" }}>
            {schema?.dialect || "SQLite"} · read-only
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="px-3 pt-3 pb-2 flex-shrink-0 relative">
        <Search
          className="absolute left-[18px] top-1/2 -translate-y-1/2 w-3.5 h-3.5"
          style={{ color: "#5a7080" }}
        />
        <input
          type="text"
          placeholder="Search tables, columns..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-md pl-8 pr-3 py-1.5 text-[11px] outline-none transition-colors"
          style={{
            backgroundColor: "#080c10",
            border: "1px solid #1e2a35",
            color: "#e8edf2",
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = "#2dd4bf")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "#1e2a35")}
        />
      </div>

      {/* Schema Tree */}
      <div className="flex-1 overflow-y-auto px-3 pb-2">
        <div
          className="pt-3 pb-1 text-[9px] font-semibold uppercase tracking-widest"
          style={{ color: "#5a7080" }}
        >
          Schema
        </div>

        {/* DB Group */}
        <div
          className="flex items-center gap-1.5 py-1.5 cursor-pointer"
          style={{ color: "#8fa3b0" }}
        >
          <ChevronDown className="w-3 h-3" style={{ color: "#5a7080" }} />
          <span className="text-[11px]" style={{ fontFamily: "'DM Mono', monospace" }}>
            {schema?.dialect || "my"}_db
          </span>
        </div>

        {filteredTables.map((table) => (
          <div key={table.name}>
            <div
              className="flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer transition-all select-none"
              style={{
                backgroundColor: activeTable === table.name ? "rgba(45,212,191,0.08)" : "transparent",
                borderRight: activeTable === table.name ? "2px solid #2dd4bf" : "2px solid transparent",
              }}
              onClick={() => toggleTable(table.name)}
              onMouseEnter={(e) => {
                if (activeTable !== table.name) {
                  e.currentTarget.style.backgroundColor = "#1c2822";
                }
              }}
              onMouseLeave={(e) => {
                if (activeTable !== table.name) {
                  e.currentTarget.style.backgroundColor = "transparent";
                }
              }}
            >
              {expandedTables.includes(table.name) ? (
                <ChevronDown className="w-3 h-3 flex-shrink-0" style={{ color: "#5a7080" }} />
              ) : (
                <ChevronRight className="w-3 h-3 flex-shrink-0" style={{ color: "#5a7080" }} />
              )}
              <div
                className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                style={{
                  backgroundColor: activeTable === table.name ? "#2dd4bf" : "#5a7080",
                }}
              />
              <span
                className="text-[11px] flex-1 truncate"
                style={{
                  color: activeTable === table.name ? "#2dd4bf" : "#8fa3b0",
                  fontFamily: "'DM Mono', monospace",
                }}
              >
                {table.name}
              </span>
              <span
                className="text-[9px] flex-shrink-0"
                style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
              >
                {table.count.toLocaleString()}
              </span>
            </div>

            {expandedTables.includes(table.name) && (
              <div className="pl-7 pr-2 pb-1">
                {table.columns.map((col) => (
                  <div
                    key={col.name}
                    className="flex items-center gap-2 py-0.5 cursor-pointer group"
                  >
                    <span
                      className="text-[9px] px-1 py-px rounded font-medium flex-shrink-0"
                      style={{
                        backgroundColor: "#080c10",
                        border: "1px solid #1e2a35",
                        color: "#5a7080",
                      }}
                    >
                      {col.type}
                    </span>
                    <span
                      className="text-[10px] truncate"
                      style={{ color: "#8fa3b0", fontFamily: "'DM Mono', monospace" }}
                    >
                      {col.name}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Suggestions */}
      <div
        className="p-3 flex-shrink-0"
        style={{ borderTop: "1px solid #1e2a35" }}
      >
        <div
          className="text-[9px] uppercase tracking-widest mb-2"
          style={{ color: "#5a7080" }}
        >
          Suggested
        </div>
        {SUGGESTIONS.map((suggestion) => (
          <div
            key={suggestion}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md mb-1 cursor-pointer transition-all text-[11px]"
            style={{
              backgroundColor: "#080c10",
              border: "1px solid #1e2a35",
              color: "#8fa3b0",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "rgba(45,212,191,0.25)";
              e.currentTarget.style.backgroundColor = "rgba(45,212,191,0.04)";
              e.currentTarget.style.color = "#2dd4bf";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "#1e2a35";
              e.currentTarget.style.backgroundColor = "#080c10";
              e.currentTarget.style.color = "#8fa3b0";
            }}
          >
            <span style={{ color: "#2dd4bf" }}>✦</span>
            {suggestion}
          </div>
        ))}
      </div>
    </div>
  );
}

function getTypeColor(type: string): string {
  const t = type?.toLowerCase() || "";
  if (t.includes("int")) return "bg-[#080c10] text-[#5a7080] border-[#1e2a35]";
  if (t.includes("text") || t.includes("varchar")) return "bg-[#080c10] text-[#5a7080] border-[#1e2a35]";
  if (t.includes("real") || t.includes("float") || t.includes("double") || t.includes("decimal")) return "bg-[#080c10] text-[#5a7080] border-[#1e2a35]";
  if (t.includes("date") || t.includes("time")) return "bg-[#080c10] text-[#5a7080] border-[#1e2a35]";
  return "bg-[#080c10] text-[#5a7080] border-[#1e2a35]";
}
