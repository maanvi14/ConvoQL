"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
  AreaChart,
} from "recharts";
import {
  BarChart3,
  LineChartIcon,
  PieChartIcon,
  Table2,
  Download,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface AutoChartProps {
  data: {
    columns: string[];
    rows: Record<string, any>[];
  };
  chartType: "bar" | "line" | "pie" | "table" | "area";
  title?: string;
}

const COLORS = [
  "#2dd4bf",   // teal-400
  "#60a5fa",   // blue-400
  "#c084fc",   // purple-400
  "#34d399",   // emerald-400
  "#f87171",   // red-400
  "#f59e0b",   // amber-400
  "#0ea5e9",   // sky-500
  "#f472b6",   // pink-400
];

// ── Helpers ──────────────────────────────────────────────

function isDateColumn(col: string, sampleVal: any): boolean {
  if (typeof sampleVal !== "string") return false;
  const c = col.toLowerCase();
  return c.includes("date") || c.includes("month") || c.includes("year") || c.includes("time");
}

function parseDate(val: string): Date | null {
  if (!val) return null;
  // Try ISO, "2026-03", "March 2026", etc.
  const d = new Date(val);
  if (!isNaN(d.getTime())) return d;
  // Try "2026-03" format
  if (/^\d{4}-\d{2}$/.test(val)) {
    const dd = new Date(val + "-01");
    if (!isNaN(dd.getTime())) return dd;
  }
  return null;
}

function formatCurrency(v: number): string {
  const absVal = Math.abs(v);
  if (absVal >= 100000) return `₹${(absVal / 100000).toFixed(1)}L`;
  if (absVal >= 1000) return `₹${(absVal / 1000).toFixed(1)}k`;
  return `₹${absVal.toFixed(0)}`;
}

function formatCurrencyFull(v: number): string {
  return `₹${Math.abs(v).toLocaleString("en-IN")}`;
}

// Smart tick formatter that doesn't collapse small values to 0
function yAxisTickFormatter(v: number): string {
  const absVal = Math.abs(v);
  if (absVal === 0) return "₹0";
  if (absVal >= 100000) return `₹${(absVal / 100000).toFixed(0)}L`;
  if (absVal >= 1000) return `₹${(absVal / 1000).toFixed(0)}k`;
  return `₹${absVal.toFixed(0)}`;
}

// ── Component ────────────────────────────────────────────

export default function AutoChart({ data, chartType: initialType, title }: AutoChartProps) {
  const [activeChart, setActiveChart] = useState<"bar" | "line" | "pie" | "table" | "area">(
    initialType === "table" ? "bar" : initialType
  );

  if (!data || !data.rows || data.rows.length === 0) {
    return (
      <div className="rounded-xl p-6 text-center" style={{ backgroundColor: "#141b22", border: "1px solid #243040" }}>
        <p style={{ color: "#5a7080", fontSize: "12px" }}>No data available for visualization</p>
      </div>
    );
  }

  const columns = data.columns || [];
  const rows = data.rows || [];

  // ── Smart column detection ─────────────────────────────

  // Find date column
  const dateCol = columns.find(c => isDateColumn(c, rows[0]?.[c]));

  // Find numeric columns (treat amount specially — always absolute)
  const numericCols = columns.filter(c => {
    const val = rows[0]?.[c];
    return typeof val === "number" || (typeof val === "string" && !isNaN(Number(val)) && val !== "");
  });

  // Primary value column: prefer one with "amount", "total", "sum" in name
  const valueCol =
    numericCols.find(c => /amount|total|sum|spend|cost|price/i.test(c)) ||
    numericCols[0];

  // Label column: string column that's not date and not the value
  const labelCol =
    columns.find(c => {
      if (c === valueCol || c === dateCol) return false;
      return typeof rows[0]?.[c] === "string";
    }) ||
    dateCol ||
    columns.find(c => c !== valueCol) ||
    columns[0];

  // ── Determine if data is time-series ───────────────────
  const isTimeSeries = useMemo(() => {
    if (!dateCol) return false;
    const parsed = rows.map(r => parseDate(r[dateCol])).filter(Boolean);
    return parsed.length >= 2;
  }, [dateCol, rows]);

  // ── Build chart data ───────────────────────────────────
  const chartData = useMemo(() => {
    const processed = rows.map((row) => {
      const rawValue = row[valueCol];
      // Always use absolute value for spending visualizations
      const numValue = typeof rawValue === "number" ? Math.abs(rawValue) : Math.abs(Number(rawValue) || 0);

      let name: string;
      if (dateCol && parseDate(row[dateCol])) {
        const d = parseDate(row[dateCol])!;
        name = d.toLocaleDateString("en-IN", { month: "short", year: "2-digit" });
      } else {
        name = String(row[labelCol] ?? row[dateCol] ?? "Unknown");
      }

      return {
        name,
        value: numValue,
        rawValue,
        ...row,
      };
    });

    // Sort by date if time-series
    if (isTimeSeries && dateCol) {
      return processed.sort((a, b) => {
        const da = parseDate(a[dateCol]);
        const db = parseDate(b[dateCol]);
        if (da && db) return da.getTime() - db.getTime();
        return 0;
      });
    }

    return processed;
  }, [rows, valueCol, labelCol, dateCol, isTimeSeries]);

  // ── Auto-suggest better chart type ─────────────────────
  const suggestedChart = useMemo(() => {
    if (activeChart !== initialType && initialType !== "table") return activeChart;
    if (isTimeSeries) return "line";
    if (chartData.length <= 5) return "pie";
    return "bar";
  }, [isTimeSeries, chartData.length, activeChart, initialType]);

  // ── Export handler ─────────────────────────────────────
  const handleExport = (format: string) => {
    let content = "";
    let mimeType = "";
    let extension = "";

    switch (format) {
      case "csv":
        content = [
          columns.join(","),
          ...rows.map(row =>
            columns.map(col => {
              const val = row[col];
              if (val === null || val === undefined) return "";
              const s = String(val);
              return s.includes(",") ? `"${s}"` : s;
            }).join(",")
          ),
        ].join("\n");
        mimeType = "text/csv";
        extension = "csv";
        break;
      case "json":
        content = JSON.stringify(rows, null, 2);
        mimeType = "application/json";
        extension = "json";
        break;
      case "md":
        content = [
          `| ${columns.join(" | ")} |`,
          `| ${columns.map(() => "---").join(" | ")} |`,
          ...rows.map(
            row =>
              `| ${columns.map(col => (row[col] !== undefined ? String(row[col]) : "")).join(" | ")} |`
          ),
        ].join("\n");
        mimeType = "text/markdown";
        extension = "md";
        break;
      default:
        content = JSON.stringify(rows, null, 2);
        mimeType = "text/plain";
        extension = "txt";
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `export_${title?.replace(/\s+/g, "_").toLowerCase() || "data"}.${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ── Render chart ───────────────────────────────────────
  const renderChart = () => {
    const commonTooltipStyle = {
      backgroundColor: "#141b22",
      border: "1px solid #243040",
      borderRadius: "8px",
      fontSize: "12px",
      color: "#e8edf2",
      fontFamily: "'DM Mono', monospace",
      boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
    };

    const commonXAxisProps = {
      tick: { fill: "#5a7080", fontSize: 11, fontFamily: "'DM Mono', monospace" },
      axisLine: { stroke: "#243040" },
      tickLine: false,
    };

    const commonYAxisProps = {
      tick: { fill: "#5a7080", fontSize: 11, fontFamily: "'DM Mono', monospace" },
      axisLine: false,
      tickLine: false,
      tickFormatter: yAxisTickFormatter,
    };

    switch (activeChart) {
      case "bar":
        return (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a35" vertical={false} />
              <XAxis dataKey="name" {...commonXAxisProps} />
              <YAxis {...commonYAxisProps} />
              <Tooltip
                cursor={{ fill: "rgba(30, 42, 53, 0.4)" }}
                contentStyle={commonTooltipStyle}
                formatter={(value: number) => [formatCurrencyFull(value), valueCol]}
                labelStyle={{ color: "#5a7080", marginBottom: "4px" }}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={60}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} stroke={COLORS[i % COLORS.length]} strokeWidth={1} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        );

      case "line":
      case "area":
        return (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2dd4bf" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#2dd4bf" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a35" vertical={false} />
              <XAxis dataKey="name" {...commonXAxisProps} />
              <YAxis {...commonYAxisProps} />
              <Tooltip
                contentStyle={commonTooltipStyle}
                formatter={(value: number) => [formatCurrencyFull(value), valueCol]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#2dd4bf"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#colorValue)"
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#2dd4bf"
                strokeWidth={2.5}
                dot={{ fill: "#2dd4bf", r: 4, strokeWidth: 0 }}
                activeDot={{ r: 6, fill: "#5eead4", stroke: "#2dd4bf", strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        );

      case "pie":
        return (
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="45%"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={3}
                dataKey="value"
                stroke="#080c10"
                strokeWidth={3}
              >
                {chartData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={commonTooltipStyle}
                formatter={(value: number, name: string) => [formatCurrencyFull(value), name]}
              />
              <Legend
                verticalAlign="bottom"
                height={36}
                iconType="circle"
                iconSize={8}
                formatter={(value) => (
                  <span style={{ color: "#8fa3b0", fontSize: "11px", fontFamily: "'DM Mono', monospace" }}>
                    {value}
                  </span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        );

      case "table":
        return (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ borderBottom: "1px solid #243040" }}>
                  {columns.map((col) => (
                    <th
                      key={col}
                      className="text-left py-2.5 px-3 font-medium uppercase tracking-wider"
                      style={{ color: "#5a7080", fontSize: "9px", backgroundColor: "#0e1318" }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr
                    key={i}
                    style={{ borderBottom: "1px solid #1e2a35" }}
                    className="hover:bg-[#1c2822] transition-colors"
                  >
                    {columns.map((col) => {
                      const val = row[col];
                      const isNumeric = typeof val === "number" || (typeof val === "string" && !isNaN(Number(val)));
                      const displayVal = isNumeric ? formatCurrencyFull(Number(val)) : String(val ?? "-");
                      return (
                        <td
                          key={col}
                          className="py-2.5 px-3 font-mono"
                          style={{
                            color: isNumeric ? "#2dd4bf" : "#8fa3b0",
                            fontSize: "11px",
                          }}
                        >
                          {displayVal}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
    }
  };

  const chartOptions: { type: typeof activeChart; icon: React.ReactNode; label: string }[] = [
    { type: "bar", icon: <BarChart3 className="w-3.5 h-3.5" />, label: "Bar" },
    { type: "line", icon: <LineChartIcon className="w-3.5 h-3.5" />, label: "Line" },
    { type: "pie", icon: <PieChartIcon className="w-3.5 h-3.5" />, label: "Pie" },
    { type: "table", icon: <Table2 className="w-3.5 h-3.5" />, label: "Table" },
  ];

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ border: "1px solid #243040", backgroundColor: "#141b22" }}
    >
      {/* Chart Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: "1px solid #243040", backgroundColor: "#0e1318" }}
      >
        <span className="text-[12px] font-medium" style={{ color: "#e8edf2" }}>
          {title || "Chart"}
        </span>
        <div className="flex items-center gap-1">
          {chartOptions.map((opt) => (
            <button
              key={opt.type}
              onClick={() => setActiveChart(opt.type)}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition-all",
                activeChart === opt.type ? "text-[#2dd4bf]" : "text-[#5a7080] hover:text-[#8fa3b0]"
              )}
              style={{
                backgroundColor: activeChart === opt.type ? "rgba(45,212,191,0.08)" : "transparent",
                border: activeChart === opt.type ? "1px solid rgba(45,212,191,0.15)" : "1px solid transparent",
              }}
            >
              {opt.icon}
              {opt.label}
            </button>
          ))}
          <div className="w-px h-4 mx-1" style={{ backgroundColor: "#243040" }} />
          <button
            onClick={() => handleExport("csv")}
            className="p-1.5 rounded-md transition-all hover:bg-[#1c2822]"
            style={{ color: "#5a7080" }}
            title="Export CSV"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Chart Content */}
      <div className="p-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeChart}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
          >
            {renderChart()}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
