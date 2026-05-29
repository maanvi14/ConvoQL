"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

export default function LandingPage() {
  const router = useRouter();
  const [typedText, setTypedText] = useState("");
  const [showMsg2, setShowMsg2] = useState(false);
  const [showMsg3, setShowMsg3] = useState(false);

  const questions = [
    "Which account had most debit transactions?",
    "Compare income vs expenses last month",
    "Show me trends in grocery spending",
    "Any anomalies in July transactions?",
  ];

  useEffect(() => {
    const t1 = setTimeout(() => setShowMsg2(true), 1800);
    const t2 = setTimeout(() => setShowMsg3(true), 2700);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []);

  useEffect(() => {
    let qi = 0,
      ci = 0,
      typing = true,
      waiting = false;
    let timer: ReturnType<typeof setTimeout>;

    const typeLoop = () => {
      if (waiting) return;
      const q = questions[qi];
      if (typing) {
        if (ci <= q.length) {
          setTypedText(q.slice(0, ci));
          ci++;
          timer = setTimeout(typeLoop, 45 + Math.random() * 30);
        } else {
          waiting = true;
          timer = setTimeout(() => {
            waiting = false;
            typing = false;
            timer = setTimeout(typeLoop, 40);
          }, 1800);
        }
      } else {
        if (ci > 0) {
          ci--;
          setTypedText(q.slice(0, ci));
          timer = setTimeout(typeLoop, 18);
        } else {
          qi = (qi + 1) % questions.length;
          typing = true;
          timer = setTimeout(typeLoop, 400);
        }
      }
    };

    const startTimer = setTimeout(typeLoop, 3200);
    return () => {
      clearTimeout(startTimer);
      clearTimeout(timer);
    };
  }, []);

  const handleTryDemo = () => {
    setTimeout(() => router.push("/chat"), 400);
  };

  return (
    <>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&family=DM+Sans:wght@300;400;500&display=swap"
          rel="stylesheet"
        />
        <style>{`html, body { overflow-y: auto; overflow-x: hidden; } html { scroll-behavior: smooth; }`}</style>
      </head>
      <div
        className="min-h-screen overflow-y-auto"
        style={{
          backgroundColor: "#080c10",
          color: "#e8edf2",
          fontFamily: "'DM Sans', system-ui, sans-serif",
          fontWeight: 300,
          lineHeight: 1.6,
        }}
      >
        {/* Grid Background */}
        <div
          className="absolute inset-0 pointer-events-none z-0"
          style={{
            backgroundImage:
              "linear-gradient(#1e2a35 1px, transparent 1px), linear-gradient(90deg, #1e2a35 1px, transparent 1px)",
            backgroundSize: "60px 60px",
            opacity: 0.2,
          }}
        />

        {/* Blob 1 */}
        <div
          className="absolute w-[500px] h-[500px] rounded-full pointer-events-none z-0"
          style={{
            background: "radial-gradient(circle, rgba(45,212,191,0.15) 0%, transparent 70%)",
            top: "-80px",
            left: "-80px",
            filter: "blur(80px)",
          }}
        />
        {/* Blob 2 */}
        <div
          className="absolute w-[400px] h-[400px] rounded-full pointer-events-none z-0"
          style={{
            background: "radial-gradient(circle, rgba(14,165,233,0.12) 0%, transparent 70%)",
            bottom: "0",
            right: "-60px",
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
          <a href="#" className="flex items-center gap-2 no-underline">
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
          </a>
          <div className="flex items-center gap-7">
            <a
              href="#how"
              className="text-xs no-underline transition-colors hover:text-[#2dd4bf]"
              style={{ color: "#8fa3b0" }}
            >
              How it works
            </a>
            <a
              href="#features"
              className="text-xs no-underline transition-colors hover:text-[#2dd4bf]"
              style={{ color: "#8fa3b0" }}
            >
              Features
            </a>
            <a
              href="#stack"
              className="text-xs no-underline transition-colors hover:text-[#2dd4bf]"
              style={{ color: "#8fa3b0" }}
            >
              Stack
            </a>
          </div>
          <a
            href="https://github.com/maanvi14/ChatSQL-AI-Powered-Data-Query-App"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3.5 py-1.5 rounded-md text-[11px] no-underline transition-all font-mono hover:border-[#2dd4bf] hover:text-[#2dd4bf]"
            style={{
              border: "1px solid #243040",
              color: "#8fa3b0",
              fontFamily: "'DM Mono', monospace",
            }}
          >
            ⌥ View source
          </a>
        </nav>

        {/* Hero */}
        <section className="relative z-10 flex flex-col items-center justify-center pt-20 pb-10 px-6 text-center">
          {/* Badge */}
          <div
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[10px] tracking-widest uppercase mb-6"
            style={{
              border: "1px solid #243040",
              color: "#2dd4bf",
              fontFamily: "'DM Mono', monospace",
              backgroundColor: "rgba(45,212,191,0.04)",
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: "#2dd4bf" }}
            />
            Agentic SQL reasoning · LangGraph · Self-correcting
          </div>

          <h1
            className="font-normal leading-[1.05] max-w-[800px] mb-5 tracking-tight"
            style={{
              fontFamily: "'Instrument Serif', Georgia, serif",
              fontSize: "clamp(44px, 6vw, 72px)",
            }}
          >
            Your database,
            <br />
            <em
              className="italic"
              style={{ color: "transparent", WebkitTextStroke: "1px #2dd4bf" }}
            >
              finally
            </em>{" "}
            in plain <span style={{ color: "#2dd4bf" }}>English</span>
          </h1>

          <p
            className="text-[15px] max-w-[500px] leading-relaxed mb-8 font-light"
            style={{ color: "#8fa3b0" }}
          >
            ConvoQL is a conversational analytics platform. Ask questions, get SQL, charts,
            trend analysis, and anomaly detection — powered by a self-correcting LangGraph
            agent.
          </p>

          <div className="flex gap-2.5 flex-wrap justify-center mb-3">
            <button
              onClick={handleTryDemo}
              className="flex items-center gap-1.5 px-6 py-3 rounded-lg text-[13px] font-medium transition-all hover:-translate-y-px"
              style={{ backgroundColor: "#2dd4bf", color: "#080c10" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.backgroundColor = "#5eead4")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.backgroundColor = "#2dd4bf")
              }
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
              >
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Try with demo data
            </button>
            <button
              className="flex items-center gap-1.5 px-6 py-3 bg-transparent rounded-lg text-[13px] transition-all hover:border-[#8fa3b0]"
              style={{
                color: "#e8edf2",
                border: "1px solid #243040",
              }}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              >
                <ellipse cx="12" cy="5" rx="9" ry="3" />
                <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
              </svg>
              Connect your database
            </button>
          </div>

          <p
            className="text-[10px] tracking-wider"
            style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
          >
            SQLite · MySQL · PostgreSQL — read-only mode, always safe
          </p>

          {/* Demo Window */}
          <div className="w-full max-w-[900px] mt-12 relative z-10">
            <div
              className="border rounded-xl overflow-hidden"
              style={{
                borderColor: "#243040",
                backgroundColor: "#0e1318",
                boxShadow: "0 40px 80px rgba(0,0,0,0.5)",
              }}
            >
              {/* Window Bar */}
              <div
                className="flex items-center gap-1.5 px-3.5 py-2.5 border-b"
                style={{ backgroundColor: "#141b22", borderColor: "#1e2a35" }}
              >
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: "#f87171" }}
                />
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: "#fbbf24" }}
                />
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: "#34d399" }}
                />
                <div
                  className="flex-1 mx-2.5 rounded px-2.5 py-1 text-[10px]"
                  style={{
                    backgroundColor: "#080c10",
                    border: "1px solid #1e2a35",
                    color: "#5a7080",
                    fontFamily: "'DM Mono', monospace",
                  }}
                >
                  convoql.vercel.app/chat
                </div>
              </div>

              {/* Window Body */}
              <div className="flex h-[380px]">
                {/* Sidebar */}
                <div
                  className="w-40 border-r p-3.5 text-[10px] flex-shrink-0 flex flex-col"
                  style={{
                    borderColor: "#1e2a35",
                    fontFamily: "'DM Mono', monospace",
                  }}
                >
                  <div
                    className="tracking-widest uppercase text-[9px] mb-2.5"
                    style={{ color: "#5a7080" }}
                  >
                    Tables
                  </div>
                  <div
                    className="px-2 py-1 rounded cursor-pointer mb-0.5 flex items-center gap-1.5"
                    style={{
                      color: "#2dd4bf",
                      backgroundColor: "rgba(45,212,191,0.08)",
                      border: "1px solid rgba(45,212,191,0.15)",
                    }}
                  >
                    ⊞ transactions
                  </div>
                  <div
                    className="px-2 py-1 rounded cursor-pointer mb-0.5 flex items-center gap-1.5 hover:bg-[#141b22] transition-colors"
                    style={{ color: "#8fa3b0" }}
                  >
                    ⊞ accounts
                  </div>
                  <div
                    className="px-2 py-1 rounded cursor-pointer mb-0.5 flex items-center gap-1.5 hover:bg-[#141b22] transition-colors"
                    style={{ color: "#8fa3b0" }}
                  >
                    ⊞ categories
                  </div>
                </div>

                {/* Chat */}
                <div
                  className="flex-1 flex flex-col overflow-hidden"
                  style={{ backgroundColor: "#0e1318" }}
                >
                  <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-3.5">
                    {/* User msg */}
                    <div className="flex gap-2 items-start flex-row-reverse">
                      <div
                        className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium flex-shrink-0"
                        style={{
                          backgroundColor: "#141b22",
                          border: "1px solid #1e2a35",
                          color: "#8fa3b0",
                          fontFamily: "'DM Mono', monospace",
                        }}
                      >
                        U
                      </div>
                      <div
                        className="max-w-[88%] px-3 py-2 rounded-[10px] text-[12px] leading-relaxed"
                        style={{
                          backgroundColor: "rgba(45,212,191,0.08)",
                          border: "1px solid rgba(45,212,191,0.12)",
                          color: "#e8edf2",
                        }}
                      >
                        Show my spending by category this month
                      </div>
                    </div>

                    {/* AI msg */}
                    <div className="flex gap-2 items-start">
                      <div
                        className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium flex-shrink-0"
                        style={{
                          backgroundColor: "rgba(45,212,191,0.1)",
                          border: "1px solid rgba(45,212,191,0.2)",
                          color: "#2dd4bf",
                          fontFamily: "'DM Mono', monospace",
                        }}
                      >
                        AI
                      </div>
                      <div
                        className="max-w-[88%] px-3 py-2 rounded-[10px] text-[12px] leading-relaxed"
                        style={{
                          backgroundColor: "#141b22",
                          border: "1px solid #1e2a35",
                          color: "#e8edf2",
                        }}
                      >
                        Found 5 categories. Groceries leads at ₹8,200.
                        <div
                          className="mt-1.5 p-1.5 rounded font-mono text-[10px] leading-relaxed"
                          style={{
                            backgroundColor: "#080c10",
                            border: "1px solid #243040",
                            borderLeft: "2px solid #f59e0b",
                            color: "#f59e0b",
                            fontFamily: "'DM Mono', monospace",
                          }}
                        >
                          <span style={{ color: "#f59e0b" }}>SELECT</span>{" "}
                          <span style={{ color: "#67e8f9" }}>category</span>,{" "}
                          <span style={{ color: "#c084fc" }}>SUM</span>(
                          <span style={{ color: "#67e8f9" }}>amount</span>){" "}
                          <span style={{ color: "#f59e0b" }}>AS</span> total
                          <br />
                          <span style={{ color: "#f59e0b" }}>FROM</span> transactions
                          <br />
                          <span style={{ color: "#f59e0b" }}>WHERE</span>{" "}
                          <span style={{ color: "#67e8f9" }}>date</span> &gt;={" "}
                          <span style={{ color: "#34d399" }}>&apos;2025-07-01&apos;</span>
                          <br />
                          <span style={{ color: "#f59e0b" }}>GROUP BY</span>{" "}
                          <span style={{ color: "#67e8f9" }}>category</span>
                        </div>
                        <div className="flex items-end gap-1 h-[42px] px-0.5 mt-2">
                          {[100, 65, 48, 38, 22].map((h, i) => (
                            <div
                              key={i}
                              className="flex-1 rounded-t"
                              style={{
                                height: `${h}%`,
                                backgroundColor:
                                  i === 0
                                    ? "rgba(45,212,191,0.32)"
                                    : "rgba(45,212,191,0.18)",
                                borderTop:
                                  i === 0
                                    ? "1px solid #2dd4bf"
                                    : "1px solid rgba(45,212,191,0.35)",
                              }}
                            />
                          ))}
                        </div>
                        <div
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] mt-1.5 tracking-wide"
                          style={{
                            backgroundColor: "rgba(52,211,153,0.08)",
                            border: "1px solid rgba(52,211,153,0.15)",
                            color: "#34d399",
                            fontFamily: "'DM Mono', monospace",
                          }}
                        >
                          ✓ 5 rows · 12ms
                        </div>
                      </div>
                    </div>

                    {/* Fade-in messages */}
                    <div
                      className={`flex gap-2 items-start flex-row-reverse transition-opacity duration-500 ${
                        showMsg2 ? "opacity-100" : "opacity-0"
                      }`}
                    >
                      <div
                        className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium flex-shrink-0"
                        style={{
                          backgroundColor: "#141b22",
                          border: "1px solid #1e2a35",
                          color: "#8fa3b0",
                          fontFamily: "'DM Mono', monospace",
                        }}
                      >
                        U
                      </div>
                      <div
                        className="max-w-[88%] px-3 py-2 rounded-[10px] text-[12px] leading-relaxed"
                        style={{
                          backgroundColor: "rgba(45,212,191,0.08)",
                          border: "1px solid rgba(45,212,191,0.12)",
                          color: "#e8edf2",
                        }}
                      >
                        Any unusual transactions?
                      </div>
                    </div>

                    <div
                      className={`flex gap-2 items-start transition-opacity duration-500 ${
                        showMsg3 ? "opacity-100" : "opacity-0"
                      }`}
                    >
                      <div
                        className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium flex-shrink-0"
                        style={{
                          backgroundColor: "rgba(45,212,191,0.1)",
                          border: "1px solid rgba(45,212,191,0.2)",
                          color: "#2dd4bf",
                          fontFamily: "'DM Mono', monospace",
                        }}
                      >
                        AI
                      </div>
                      <div
                        className="max-w-[88%] px-3 py-2 rounded-[10px] text-[12px] leading-relaxed"
                        style={{
                          backgroundColor: "#141b22",
                          border: "1px solid #1e2a35",
                          color: "#e8edf2",
                        }}
                      >
                        Agent retried once — fixed date filter automatically.
                        <div
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] mt-1 tracking-wide"
                          style={{
                            backgroundColor: "rgba(248,113,113,0.08)",
                            border: "1px solid rgba(248,113,113,0.15)",
                            color: "#f87171",
                            fontFamily: "'DM Mono', monospace",
                          }}
                        >
                          ⚠ Amazon ₹3,200 — 2.8σ above usual shopping spend
                        </div>
                        <div
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] mt-1 tracking-wide"
                          style={{
                            backgroundColor: "rgba(52,211,153,0.08)",
                            border: "1px solid rgba(52,211,153,0.15)",
                            color: "#34d399",
                            fontFamily: "'DM Mono', monospace",
                          }}
                        >
                          ✓ Anomaly detected · self-corrected
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Input */}
                  <div
                    className="px-3.5 py-2.5 border-t flex items-center gap-2"
                    style={{
                      borderColor: "#1e2a35",
                      backgroundColor: "#141b22",
                    }}
                  >
                    <input
                      readOnly
                      value={typedText}
                      placeholder="Ask anything about your data..."
                      className="flex-1 rounded-lg px-3 py-2 text-[11px] outline-none"
                      style={{
                        backgroundColor: "#080c10",
                        border: "1px solid #1e2a35",
                        color: "#5a7080",
                      }}
                    />
                    <button
                      className="w-[30px] h-[30px] rounded-md flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: "#2dd4bf" }}
                    >
                      <svg
                        width="13"
                        height="13"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#080c10"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                      >
                        <line x1="22" y1="2" x2="11" y2="13" />
                        <polygon points="22 2 15 22 11 13 2 9 22 2" />
                      </svg>
                    </button>
                  </div>
                </div>

                {/* SQL Panel */}
                <div
                  className="w-[200px] border-l text-[10px] flex-shrink-0 flex flex-col"
                  style={{
                    borderColor: "#1e2a35",
                    fontFamily: "'DM Mono', monospace",
                  }}
                >
                  <div
                    className="px-3 py-2.5 border-b flex items-center justify-between"
                    style={{ borderColor: "#1e2a35" }}
                  >
                    <span
                      className="text-[9px] tracking-widest uppercase"
                      style={{ color: "#5a7080" }}
                    >
                      Generated SQL
                    </span>
                    <button
                      className="px-1.5 py-0.5 rounded bg-transparent text-[9px] cursor-pointer font-mono transition-all hover:border-[#2dd4bf] hover:text-[#2dd4bf]"
                      style={{
                        border: "1px solid #1e2a35",
                        color: "#5a7080",
                        fontFamily: "'DM Mono', monospace",
                      }}
                    >
                      copy
                    </button>
                  </div>
                  <div className="p-3 flex-1 overflow-auto">
                    <div className="leading-relaxed" style={{ color: "#8fa3b0" }}>
                      <span style={{ color: "#f59e0b" }}>SELECT</span>
                      <br />
                      &nbsp;&nbsp;category,
                      <br />
                      &nbsp;&nbsp;<span style={{ color: "#c084fc" }}>SUM</span>(amount)
                      <br />
                      &nbsp;&nbsp;<span style={{ color: "#f59e0b" }}>AS</span> total
                      <br />
                      <span style={{ color: "#f59e0b" }}>FROM</span>
                      <br />
                      &nbsp;&nbsp;transactions
                      <br />
                      <span style={{ color: "#f59e0b" }}>WHERE</span>
                      <br />
                      &nbsp;&nbsp;date &gt;={" "}
                      <span style={{ color: "#34d399" }}>&apos;07-01&apos;</span>
                      <br />
                      <span style={{ color: "#f59e0b" }}>GROUP BY</span>
                      <br />
                      &nbsp;&nbsp;category
                    </div>
                    <div
                      className="inline-block px-1.5 py-0.5 rounded text-[9px] mt-2"
                      style={{
                        backgroundColor: "rgba(52,211,153,0.07)",
                        border: "1px solid rgba(52,211,153,0.12)",
                        color: "#34d399",
                      }}
                    >
                      ✓ read-only · safe
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Stats */}
        <div className="relative z-10 px-6 pb-16">
          <div
            className="flex justify-center max-w-[660px] mx-auto border rounded-xl overflow-hidden"
            style={{
              borderColor: "#243040",
              backgroundColor: "#0e1318",
            }}
          >
            {[
              { num: "4", label: "Agent nodes" },
              { num: "~58%", label: "Token reduction via RAG" },
              { num: "3×", label: "SQL self-correction retries" },
              { num: "<200ms", label: "First token latency" },
            ].map((stat, i) => (
              <div
                key={i}
                className="flex-1 p-5 text-center"
                style={{
                  borderRight: i < 3 ? "1px solid #1e2a35" : "none",
                }}
              >
                <span
                  className="block leading-none mb-1"
                  style={{
                    fontFamily: "'Instrument Serif', Georgia, serif",
                    fontSize: "30px",
                    color: "#2dd4bf",
                  }}
                >
                  {stat.num}
                </span>
                <span
                  className="text-[11px] tracking-wide"
                  style={{ color: "#5a7080" }}
                >
                  {stat.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* How it works */}
        <section id="how" className="relative z-10 py-16 px-6">
          <span
            className="block text-center text-[10px] tracking-widest uppercase mb-3.5"
            style={{ color: "#2dd4bf", fontFamily: "'DM Mono', monospace" }}
          >
            How it works
          </span>
          <h2
            className="font-normal text-center leading-tight mb-3.5 tracking-tight"
            style={{
              fontFamily: "'Instrument Serif', Georgia, serif",
              fontSize: "clamp(32px, 3.5vw, 44px)",
            }}
          >
            Not a wrapper. A real agent.
          </h2>
          <p
            className="text-center text-[14px] max-w-[480px] mx-auto mb-12 leading-relaxed"
            style={{ color: "#8fa3b0" }}
          >
            Every query runs through a 4-node LangGraph graph — observable, testable, and
            fully under your control.
          </p>

          <div
            className="grid grid-cols-4 gap-px max-w-[860px] mx-auto border rounded-xl overflow-hidden"
            style={{ borderColor: "#1e2a35", backgroundColor: "#1e2a35" }}
          >
            {[
              {
                num: "01",
                title: "Schema-aware retrieval",
                desc: "Table names, columns, and sample values are embedded into pgvector. Only relevant schema chunks are injected into the prompt.",
                icon: (
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#2dd4bf"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  >
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                ),
              },
              {
                num: "02",
                title: "SQL generation",
                desc: "The planner decomposes multi-part questions. The generator produces SQL grounded in your actual schema.",
                icon: (
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#2dd4bf"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  >
                    <polyline points="16 18 22 12 16 6" />
                    <polyline points="8 6 2 12 8 18" />
                  </svg>
                ),
              },
              {
                num: "03",
                title: "Validation + self-correction",
                desc: "SQL is checked for safety and correctness via EXPLAIN. On failure, the error feeds back to the generator — up to 3 retries.",
                icon: (
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#2dd4bf"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  >
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                ),
              },
              {
                num: "04",
                title: "Insight synthesis",
                desc: "Results pass through anomaly detection (z-score), trend analysis (MoM), and auto chart classification before streaming to UI.",
                icon: (
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#2dd4bf"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  >
                    <line x1="18" y1="20" x2="18" y2="10" />
                    <line x1="12" y1="20" x2="12" y2="4" />
                    <line x1="6" y1="20" x2="6" y2="14" />
                  </svg>
                ),
              },
            ].map((step, i) => (
              <div
                key={i}
                className="p-6 hover:bg-[#141b22] transition-colors"
                style={{ backgroundColor: "#0e1318" }}
              >
                <div
                  className="text-[10px] mb-3 tracking-wide"
                  style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
                >
                  {step.num}
                </div>
                <div
                  className="w-9 h-9 border rounded-lg flex items-center justify-center mb-3"
                  style={{ borderColor: "#243040", backgroundColor: "#080c10" }}
                >
                  {step.icon}
                </div>
                <h3
                  className="text-[13px] font-medium mb-1.5"
                  style={{ color: "#e8edf2" }}
                >
                  {step.title}
                </h3>
                <p
                  className="text-[11px] leading-relaxed"
                  style={{ color: "#8fa3b0" }}
                >
                  {step.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Features */}
        <section
          id="features"
          className="relative z-10 py-16 px-6 border-y"
          style={{
            backgroundColor: "#0e1318",
            borderColor: "#1e2a35",
          }}
        >
          <span
            className="block text-center text-[10px] tracking-widest uppercase mb-3.5"
            style={{ color: "#2dd4bf", fontFamily: "'DM Mono', monospace" }}
          >
            Features
          </span>
          <h2
            className="font-normal text-center leading-tight mb-3.5 tracking-tight"
            style={{
              fontFamily: "'Instrument Serif', Georgia, serif",
              fontSize: "clamp(32px, 3.5vw, 44px)",
            }}
          >
            Built for engineers,
            <br />
            readable by anyone
          </h2>
          <p
            className="text-center text-[14px] max-w-[480px] mx-auto mb-12 leading-relaxed"
            style={{ color: "#8fa3b0" }}
          >
            Every feature was designed to be explainable in an interview and demonstrable in
            a live demo.
          </p>

          <div className="grid grid-cols-3 gap-3.5 max-w-[900px] mx-auto">
            {[
              {
                tag: "AI",
                tagStyle: {
                  backgroundColor: "rgba(45,212,191,0.08)",
                  color: "#2dd4bf",
                  borderColor: "rgba(45,212,191,0.15)",
                },
                title: "LangGraph agent graph",
                desc: "Explicit 4-node graph — planner, generator, validator, synthesizer. Every step is logged, observable via LangSmith, and independently testable.",
              },
              {
                tag: "Performance",
                tagStyle: {
                  backgroundColor: "rgba(14,165,233,0.08)",
                  color: "#0ea5e9",
                  borderColor: "rgba(14,165,233,0.15)",
                },
                title: "Semantic query caching",
                desc: "Questions are embedded and checked against Redis before hitting the LLM. Semantically similar queries (>0.92 cosine similarity) return cached results instantly.",
              },
              {
                tag: "Safety",
                tagStyle: {
                  backgroundColor: "rgba(248,113,113,0.08)",
                  color: "#f87171",
                  borderColor: "rgba(248,113,113,0.15)",
                },
                title: "Read-only SQL enforcement",
                desc: "Every generated query is blocked from writes at two layers: a rule-based allowlist and a read-only database user. No DROP, DELETE, or INSERT ever runs.",
              },
              {
                tag: "AI",
                tagStyle: {
                  backgroundColor: "rgba(45,212,191,0.08)",
                  color: "#2dd4bf",
                  borderColor: "rgba(45,212,191,0.15)",
                },
                title: "Schema-aware RAG",
                desc: "Your schema is chunked and embedded into pgvector at startup. Retrieval pulls only the relevant tables — cutting token usage ~58% vs full-schema prompting.",
              },
              {
                tag: "AI",
                tagStyle: {
                  backgroundColor: "rgba(45,212,191,0.08)",
                  color: "#2dd4bf",
                  borderColor: "rgba(45,212,191,0.15)",
                },
                title: "Anomaly detection",
                desc: "After every query, numeric columns are checked against a 30-day rolling z-score. Statistical outliers surface automatically — no extra questions needed.",
              },
              {
                tag: "Performance",
                tagStyle: {
                  backgroundColor: "rgba(14,165,233,0.08)",
                  color: "#0ea5e9",
                  borderColor: "rgba(14,165,233,0.15)",
                },
                title: "SSE streaming",
                desc: "Tokens stream from FastAPI → Next.js via Server-Sent Events using the Vercel AI SDK. Sub-200ms time to first token, no polling, no refresh.",
              },
            ].map((feat, i) => (
              <div
                key={i}
                className="p-5 border rounded-xl hover:border-[#243040] hover:bg-[#141b22] hover:-translate-y-0.5 transition-all cursor-default"
                style={{
                  borderColor: "#1e2a35",
                  backgroundColor: "#0e1318",
                }}
              >
                <span
                  className="text-[9px] px-2 py-0.5 rounded-full inline-block tracking-wider uppercase mb-3 border"
                  style={{
                    fontFamily: "'DM Mono', monospace",
                    ...feat.tagStyle,
                  }}
                >
                  {feat.tag}
                </span>
                <h3
                  className="text-[13px] font-medium mb-1.5"
                  style={{ color: "#e8edf2" }}
                >
                  {feat.title}
                </h3>
                <p
                  className="text-[11px] leading-relaxed"
                  style={{ color: "#8fa3b0" }}
                >
                  {feat.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Stack */}
        <section id="stack" className="relative z-10 py-16 px-6">
          <span
            className="block text-center text-[10px] tracking-widest uppercase mb-3.5"
            style={{ color: "#2dd4bf", fontFamily: "'DM Mono', monospace" }}
          >
            Tech stack
          </span>
          <h2
            className="font-normal text-center leading-tight mb-3.5 tracking-tight"
            style={{
              fontFamily: "'Instrument Serif', Georgia, serif",
              fontSize: "clamp(32px, 3.5vw, 44px)",
            }}
          >
            Modern, separable,
            <br />
            production-ready
          </h2>
          <p
            className="text-center text-[14px] max-w-[480px] mx-auto mb-12 leading-relaxed"
            style={{ color: "#8fa3b0" }}
          >
            Every technology choice is intentional and can be justified in a system design
            conversation.
          </p>

          <div className="flex flex-wrap gap-2 justify-center max-w-[660px] mx-auto">
            {[
              { name: "Next.js 14", color: "#61dafb" },
              { name: "Tailwind CSS", color: "#2dd4bf" },
              { name: "shadcn/ui", color: "#6366f1" },
              { name: "Vercel AI SDK", color: "#ef4444" },
              { name: "FastAPI", color: "#009688" },
              { name: "LangGraph", color: "#f59e0b" },
              { name: "pgvector / Chroma", color: "#8b5cf6" },
              { name: "Redis (Upstash)", color: "#dc2626" },
              { name: "LangSmith tracing", color: "#22c55e" },
              { name: "Groq · LLaMA 3", color: "#0ea5e9" },
              { name: "SQLAlchemy + pool", color: "#64748b" },
              { name: "Docker Compose", color: "#f97316" },
            ].map((tech, i) => (
              <div
                key={i}
                className="flex items-center gap-1.5 px-3.5 py-1.5 border rounded-full text-[11px] hover:border-[#2dd4bf] hover:text-[#2dd4bf] transition-all cursor-default"
                style={{
                  borderColor: "#243040",
                  color: "#8fa3b0",
                  backgroundColor: "#0e1318",
                  fontFamily: "'DM Mono', monospace",
                }}
              >
                <div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: tech.color }}
                />
                {tech.name}
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <div className="relative z-10 text-center py-20 px-6">
          <div
            className="absolute pointer-events-none"
            style={{
              width: "400px",
              height: "240px",
              background:
                "radial-gradient(ellipse, rgba(45,212,191,0.05) 0%, transparent 70%)",
              left: "50%",
              top: "50%",
              transform: "translate(-50%, -50%)",
            }}
          />
          <h2
            className="font-normal mb-3.5 tracking-tight leading-tight"
            style={{
              fontFamily: "'Instrument Serif', Georgia, serif",
              fontSize: "clamp(36px, 4.5vw, 54px)",
            }}
          >
            Ask your first question
            <br />
            in 30 seconds
          </h2>
          <p
            className="text-[14px] mb-7 max-w-[400px] mx-auto"
            style={{ color: "#8fa3b0" }}
          >
            No setup needed. Load the demo database and start talking to your data right now.
          </p>
          <div className="flex gap-2.5 justify-center flex-wrap">
            <button
              onClick={handleTryDemo}
              className="flex items-center gap-1.5 px-6 py-3 rounded-lg text-[13px] font-medium transition-all hover:-translate-y-px"
              style={{ backgroundColor: "#2dd4bf", color: "#080c10" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.backgroundColor = "#5eead4")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.backgroundColor = "#2dd4bf")
              }
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
              >
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Try with demo data
            </button>
            <a
              href="https://github.com/maanvi14/ChatSQL-AI-Powered-Data-Query-App"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-6 py-3 bg-transparent rounded-lg text-[13px] transition-all hover:border-[#8fa3b0] no-underline"
              style={{
                color: "#e8edf2",
                border: "1px solid #243040",
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              View source on GitHub
            </a>
          </div>
        </div>

        {/* Footer */}
        <footer
          className="relative z-10 border-t px-8 py-5 flex items-center justify-between"
          style={{ borderColor: "#1e2a35" }}
        >
          <div
            className="text-[10px] tracking-wide"
            style={{ color: "#5a7080", fontFamily: "'DM Mono', monospace" }}
          >
            ConvoQL · built by Maanvi · 2025
          </div>
          <div className="flex gap-5">
            <a
              href="https://github.com/maanvi14/ChatSQL-AI-Powered-Data-Query-App"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] no-underline transition-colors hover:text-[#e8edf2]"
              style={{ color: "#5a7080" }}
            >
              GitHub
            </a>
            <a
              href="#"
              className="text-[11px] no-underline transition-colors hover:text-[#e8edf2]"
              style={{ color: "#5a7080" }}
            >
              Architecture
            </a>
            <a
              href="#"
              className="text-[11px] no-underline transition-colors hover:text-[#e8edf2]"
              style={{ color: "#5a7080" }}
            >
              LinkedIn
            </a>
          </div>
        </footer>
      </div>
    </>
  );
}
