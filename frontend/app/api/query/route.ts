import { NextRequest, NextResponse } from "next/server";

export const runtime = "edge";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { messages, sessionId } = body;

  // Get the last user message content as the question
  const lastUserMessage = messages?.filter((m: any) => m.role === "user").pop();
  const question = lastUserMessage?.content || "";

  try {
    // Call backend directly (no SSE, simple JSON request/response)
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        session_id: sessionId || null,
      }),
    });

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status}`);
    }

    const data = await response.json();

    // Return JSON directly to client
    return NextResponse.json(data);

  } catch (error) {
    console.error("Proxy error:", error);
    return NextResponse.json(
      { error: "Failed to connect to backend" },
      { status: 500 }
    );
  }
}
