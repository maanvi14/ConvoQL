const API_BASE = (() => {
  const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  // Strip trailing /api if present (backend routes already include /api prefix)
  return url.replace(/\/api\/?$/, "");
})();
export interface QueryResponse {
  answer: string;
  explanation?: string;
  sql?: string;
  generated_sql?: string;
  has_chart?: boolean;
  has_table?: boolean;
  chart_type?: string;
  chartType?: string;
  chart_title?: string;
  chartTitle?: string;
  insight?: string;
  result?: {
    columns: string[];
    rows: Record<string, any>[];
    rowCount?: number;
    totalRows?: number;
    executionTime?: number;
  };
  columns?: string[];
  rows?: Record<string, any>[];
  row_count?: number;
  execution_time_ms?: number;
  anomaly?: string | null;
  narrative?: string | null;
  error?: string | null;
}

export interface ConnectionTestResponse {
  success: boolean;
  dialect: string;
  tables_count?: number;
  message?: string;
}

export interface ConnectionResponse {
  session_id: string;
  dialect: string;
  tables_count: number;
  message: string;
}

export async function querySync(question: string, sessionId?: string, dbUrl?: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      session_id: sessionId || null,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }

  const data = await res.json();

  // DEBUG: Log raw response (remove in production)
  console.log("[API Raw Response]", {
    has_result: !!data.result,
    result_rows: data.result?.rows?.length,
    flat_rows: data.rows?.length,
    has_chart: data.has_chart,
    chart_type: data.chart_type,
    row_count: data.row_count,
  });

  // Normalize response format for frontend
  // Priority: data.result > data.sql_result > {columns, rows from flat fields}
  const sqlResult = data.result || data.sql_result || {};
  const rows = sqlResult.rows || data.rows || [];
  const columns = sqlResult.columns || data.columns || [];

  const normalizedResult = {
    columns,
    rows,
    rowCount: rows.length,
    totalRows: rows.length,
    executionTime: data.execution_time_ms || 0,
  };

  const normalized: QueryResponse = {
    ...data,
    result: normalizedResult,
    columns,
    rows,
    row_count: rows.length,
    // Alias fields for compatibility
    sql: data.sql || data.generated_sql,
    chartType: data.chart_type || data.chartType,
    chartTitle: data.chart_title || data.chartTitle,
    has_chart: data.has_chart ?? !!data.chart_type,
    has_table: data.has_table ?? rows.length > 0,
  };

  return normalized;
}

export async function queryStream(question: string, sessionId?: string, dbUrl?: string) {
  const res = await fetch(`${API_BASE}/api/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      session_id: sessionId || null,
    }),
  });
  return res;
}

export async function getSchema() {
  const res = await fetch(`${API_BASE}/api/schema`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createSession(dbUrl?: string) {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ db_url: dbUrl || null }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ─── Connection API ───────────────────────────────────────────────

export async function testConnection(
  dbType: string,
  connectionString?: string,
  filename?: string
): Promise<ConnectionTestResponse> {
  const res = await fetch(`${API_BASE}/api/connect/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      db_type: dbType,
      connection_string: connectionString || null,
      filename: filename || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Connection test failed");
  }
  return res.json();
}

export async function connectDatabase(
  dbType: string,
  connectionString?: string,
  file?: File
): Promise<ConnectionResponse> {
  const formData = new FormData();
  formData.append("db_type", dbType);
  if (connectionString) {
    formData.append("connection_string", connectionString);
  }
  if (file) {
    formData.append("file", file);
  }

  const res = await fetch(`${API_BASE}/api/connect`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to connect database");
  }
  return res.json();
}