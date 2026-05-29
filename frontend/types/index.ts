export interface Column {
  name: string;
  type: string;
  nullable: boolean;
  sample?: string;
}

export interface Table {
  name: string;
  columns: Column[];
  rowCount?: number;
}

export interface SchemaData {
  tables: Table[];
}

export interface SQLResult {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
  executionTime: number;
}

export interface QueryResponse {
  sql: string;
  result?: SQLResult;
  explanation: string;
  followUps: string[];
  chartType?: "bar" | "line" | "pie" | "table";
  anomaly?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sql?: string;
  result?: SQLResult;
  chartType?: "bar" | "line" | "pie" | "table";
  followUps?: string[];
  anomaly?: string;
  timestamp: Date;
}
