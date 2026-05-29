"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type DBType = "sqlite" | "mysql" | "postgresql";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Official Database Icons (SVG) ──────────────────────────────

const SQLiteIcon = ({ className }: { className?: string }) => (
  <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const MySQLIcon = ({ className }: { className?: string }) => (
  <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </svg>
);

const PostgreSQLIcon = ({ className }: { className?: string }) => (
  <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="4" />
    <line x1="4.93" y1="4.93" x2="9.17" y2="9.17" />
    <line x1="14.83" y1="14.83" x2="19.07" y2="19.07" />
    <line x1="14.83" y1="9.17" x2="19.07" y2="4.93" />
    <line x1="14.83" y1="9.17" x2="18.36" y2="5.64" />
    <line x1="4.93" y1="19.07" x2="9.17" y2="14.83" />
  </svg>
);

const ShieldIcon = ({ className }: { className?: string }) => (
  <svg className={className} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

const AlertIcon = ({ className }: { className?: string }) => (
  <svg className={className} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
);

const SpinnerIcon = ({ className }: { className?: string }) => (
  <svg className={`animate-spin ${className}`} width="16" height="16" viewBox="0 0 24 24" fill="none">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
);

export default function ConnectPage() {
  const router = useRouter();
  const [dbType, setDbType] = useState<DBType>("sqlite");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);

  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState("5432");
  const [database, setDatabase] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [ssl, setSsl] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const getDefaultPort = (type: DBType) => {
    switch (type) {
      case "mysql": return "3306";
      case "postgresql": return "5432";
      default: return "";
    }
  };

  const handleTypeChange = (type: DBType) => {
    setDbType(type);
    setError(null);
    setFile(null);
    if (type !== "sqlite") {
      setPort(getDefaultPort(type));
    }
  };

  const buildConnectionString = (): string => {
    if (dbType === "sqlite") {
      return file ? `sqlite+aiosqlite:///${file.name}` : "";
    }
    const driver = dbType === "postgresql" ? "postgresql+asyncpg" : "mysql+aiomysql";
    const sslParam = ssl ? "?sslmode=require" : "";
    return `${driver}://${username}:${password}@${host}:${port}/${database}${sslParam}`;
  };

  const handleTest = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const connStr = buildConnectionString();
      const res = await fetch(`${API_BASE}/api/connect/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          db_type: dbType,
          connection_string: dbType !== "sqlite" ? connStr : undefined,
          filename: dbType === "sqlite" && file ? file.name : undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Connection failed");
      alert("✅ Connection successful!");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const connStr = buildConnectionString();
      const formData = new FormData();
      formData.append("db_type", dbType);
      if (dbType === "sqlite" && file) {
        formData.append("file", file);
      } else {
        formData.append("connection_string", connStr);
      }

      const res = await fetch(`${API_BASE}/api/connect`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to connect");

      if (data.session_id) {
        localStorage.setItem("convoql_session_id", data.session_id);
        localStorage.setItem("convoql_db_type", dbType);
      }
      router.push("/chat");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const dbOptions: { id: DBType; label: string; icon: React.ReactNode }[] = [
    { id: "sqlite", label: "SQLite", icon: <SQLiteIcon /> },
    { id: "mysql", label: "MySQL", icon: <MySQLIcon /> },
    { id: "postgresql", label: "PostgreSQL", icon: <PostgreSQLIcon /> },
  ];

  return (
    <div
      className="min-h-screen overflow-y-auto"
      style={{
        backgroundColor: "#080c10",
        color: "#e8edf2",
        fontFamily: "'DM Sans', system-ui, sans-serif",
      }}
    >
      {/* Grid Background */}
      <div
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          backgroundImage:
            "linear-gradient(#1e2a35 1px, transparent 1px), linear-gradient(90deg, #1e2a35 1px, transparent 1px)",
          backgroundSize: "60px 60px",
          opacity: 0.2,
        }}
      />

      {/* Blob */}
      <div
        className="fixed w-[500px] h-[500px] rounded-full pointer-events-none z-0"
        style={{
          background: "radial-gradient(circle, rgba(45,212,191,0.1) 0%, transparent 70%)",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          filter: "blur(80px)",
        }}
      />

      {/* Navbar */}
      <nav
        className="relative z-10 px-8 h-14 flex items-center justify-between border-b"
        style={{
          borderColor: "#1e2a35",
          backgroundColor: "rgba(8,12,16,0.9)",
        }}
      >
        <Link href="/" className="flex items-center gap-2 no-underline">
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center"
            style={{ backgroundColor: "#2dd4bf" }}
          >
            <span
              className="text-[10px] font-medium"
              style={{ color: "#080c10", fontFamily: "'DM Mono', monospace" }}
            >
              CQ
            </span>
          </div>
          <span
            className="text-sm font-medium"
            style={{ color: "#e8edf2", fontFamily: "'DM Mono', monospace" }}
          >
            ConvoQL
          </span>
        </Link>
        <Link
          href="/"
          className="text-xs no-underline transition-colors hover:text-[#2dd4bf]"
          style={{ color: "#8fa3b0" }}
        >
          ← Back to home
        </Link>
      </nav>

      {/* Main Content — scrollable */}
      <div className="relative z-10 flex flex-col items-center px-6 py-12 min-h-[calc(100vh-56px)]">
        <div className="w-full max-w-[520px] my-auto">
          {/* Header */}
          <div className="text-center mb-8">
            <div
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[10px] tracking-widest uppercase mb-4"
              style={{
                border: "1px solid #243040",
                color: "#2dd4bf",
                fontFamily: "'DM Mono', monospace",
                backgroundColor: "rgba(45,212,191,0.04)",
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#2dd4bf" }} />
              Secure · Read-only · Your data stays local
            </div>
            <h1
              className="font-normal leading-tight tracking-tight mb-2"
              style={{
                fontFamily: "'Instrument Serif', Georgia, serif",
                fontSize: "clamp(32px, 4vw, 48px)",
              }}
            >
              Connect your database
            </h1>
            <p className="text-[14px] max-w-[380px] mx-auto" style={{ color: "#8fa3b0" }}>
              Choose your database type and enter your credentials. We never store your password.
            </p>
          </div>

          {/* DB Type Selector */}
          <div
            className="flex gap-1 p-1 rounded-lg mb-6 border"
            style={{
              backgroundColor: "#0e1318",
              borderColor: "#1e2a35",
            }}
          >
            {dbOptions.map((type) => (
              <button
                key={type.id}
                onClick={() => handleTypeChange(type.id)}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-md text-[12px] font-medium transition-all"
                style={{
                  backgroundColor: dbType === type.id ? "rgba(45,212,191,0.1)" : "transparent",
                  color: dbType === type.id ? "#2dd4bf" : "#8fa3b0",
                  border: dbType === type.id ? "1px solid rgba(45,212,191,0.2)" : "1px solid transparent",
                }}
              >
                {type.icon}
                {type.label}
              </button>
            ))}
          </div>

          {/* Form Card */}
          <div
            className="border rounded-xl p-6"
            style={{
              backgroundColor: "#0e1318",
              borderColor: "#1e2a35",
            }}
          >
            {dbType === "sqlite" ? (
              <div className="space-y-4">
                <div>
                  <label
                    className="block text-[11px] tracking-wider uppercase mb-2"
                    style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
                  >
                    Database File
                  </label>
                  <div
                    className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all hover:border-[#2dd4bf] hover:bg-[rgba(45,212,191,0.02)]"
                    style={{ borderColor: file ? "#2dd4bf" : "#243040" }}
                    onClick={() => document.getElementById("file-upload")?.click()}
                  >
                    <input
                      id="file-upload"
                      type="file"
                      accept=".db,.sqlite,.sqlite3"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                    <div
                      className="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-3"
                      style={{
                        backgroundColor: file ? "rgba(45,212,191,0.1)" : "#141b22",
                        border: file ? "1px solid rgba(45,212,191,0.2)" : "1px solid #1e2a35",
                      }}
                    >
                      <SQLiteIcon className={file ? "text-[#2dd4bf]" : "text-[#5a7080]"} />
                    </div>
                    <p className="text-[13px] mb-1" style={{ color: file ? "#2dd4bf" : "#8fa3b0" }}>
                      {file ? file.name : "Drop your .db or .sqlite file here"}
                    </p>
                    <p className="text-[10px]" style={{ color: "#5a7080" }}>
                      {file ? `${(file.size / 1024).toFixed(1)} KB` : "or click to browse"}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label
                      className="block text-[11px] tracking-wider uppercase mb-1.5"
                      style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
                    >
                      Host
                    </label>
                    <input
                      type="text"
                      value={host}
                      onChange={(e) => setHost(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-[13px] outline-none transition-all focus:border-[#2dd4bf]"
                      style={{
                        backgroundColor: "#080c10",
                        border: "1px solid #1e2a35",
                        color: "#e8edf2",
                      }}
                      placeholder="localhost"
                    />
                  </div>
                  <div>
                    <label
                      className="block text-[11px] tracking-wider uppercase mb-1.5"
                      style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
                    >
                      Port
                    </label>
                    <input
                      type="text"
                      value={port}
                      onChange={(e) => setPort(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-[13px] outline-none transition-all focus:border-[#2dd4bf]"
                      style={{
                        backgroundColor: "#080c10",
                        border: "1px solid #1e2a35",
                        color: "#e8edf2",
                      }}
                      placeholder={dbType === "mysql" ? "3306" : "5432"}
                    />
                  </div>
                </div>

                <div>
                  <label
                    className="block text-[11px] tracking-wider uppercase mb-1.5"
                    style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
                  >
                    Database Name
                  </label>
                  <input
                    type="text"
                    value={database}
                    onChange={(e) => setDatabase(e.target.value)}
                    className="w-full rounded-lg px-3 py-2 text-[13px] outline-none transition-all focus:border-[#2dd4bf]"
                    style={{
                      backgroundColor: "#080c10",
                      border: "1px solid #1e2a35",
                      color: "#e8edf2",
                    }}
                    placeholder="my_database"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label
                      className="block text-[11px] tracking-wider uppercase mb-1.5"
                      style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
                    >
                      Username
                    </label>
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-[13px] outline-none transition-all focus:border-[#2dd4bf]"
                      style={{
                        backgroundColor: "#080c10",
                        border: "1px solid #1e2a35",
                        color: "#e8edf2",
                      }}
                      placeholder="root"
                    />
                  </div>
                  <div>
                    <label
                      className="block text-[11px] tracking-wider uppercase mb-1.5"
                      style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
                    >
                      Password
                    </label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full rounded-lg px-3 py-2 text-[13px] outline-none transition-all focus:border-[#2dd4bf]"
                      style={{
                        backgroundColor: "#080c10",
                        border: "1px solid #1e2a35",
                        color: "#e8edf2",
                      }}
                      placeholder="••••••••"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="ssl"
                    checked={ssl}
                    onChange={(e) => setSsl(e.target.checked)}
                    className="w-3.5 h-3.5 rounded cursor-pointer"
                    style={{ accentColor: "#2dd4bf" }}
                  />
                  <label
                    htmlFor="ssl"
                    className="text-[11px] cursor-pointer"
                    style={{ color: "#8fa3b0" }}
                  >
                    Use SSL connection
                  </label>
                </div>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div
                className="mt-4 px-3 py-2.5 rounded-lg text-[11px] flex items-center gap-2"
                style={{
                  backgroundColor: "rgba(248,113,113,0.08)",
                  border: "1px solid rgba(248,113,113,0.15)",
                  color: "#f87171",
                }}
              >
                <AlertIcon />
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2.5 mt-6">
              <button
                onClick={handleTest}
                disabled={isLoading}
                className="flex-1 py-2.5 rounded-lg text-[12px] font-medium transition-all hover:border-[#8fa3b0] disabled:opacity-50"
                style={{
                  border: "1px solid #243040",
                  color: "#8fa3b0",
                  backgroundColor: "transparent",
                }}
              >
                {isLoading ? "Testing..." : "Test connection"}
              </button>
              <button
                onClick={handleConnect}
                disabled={isLoading || (dbType === "sqlite" && !file)}
                className="flex-[2] py-2.5 rounded-lg text-[12px] font-medium transition-all hover:-translate-y-px disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  backgroundColor: "#2dd4bf",
                  color: "#080c10",
                }}
                onMouseEnter={(e) => {
                  if (!isLoading) e.currentTarget.style.backgroundColor = "#5eead4";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = "#2dd4bf";
                }}
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <SpinnerIcon />
                    Connecting...
                  </span>
                ) : (
                  "Connect & start chatting"
                )}
              </button>
            </div>
          </div>

          {/* Security Note */}
          <div
            className="mt-4 px-4 py-3 rounded-lg border flex items-start gap-2.5"
            style={{
              backgroundColor: "rgba(45,212,191,0.03)",
              borderColor: "rgba(45,212,191,0.1)",
            }}
          >
            <ShieldIcon className="flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-[11px] font-medium" style={{ color: "#2dd4bf" }}>
                Read-only mode enforced
              </p>
              <p className="text-[10px] mt-0.5" style={{ color: "#5a7080" }}>
                All queries are validated against a write-blocklist. INSERT, UPDATE, DELETE, DROP, and ALTER are automatically rejected.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
