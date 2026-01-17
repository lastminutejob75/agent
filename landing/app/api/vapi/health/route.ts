import { NextResponse } from "next/server";

/**
 * GET /api/vapi/health
 * Health check endpoint for Vapi integration
 */
export async function GET() {
  const ts = new Date().toISOString();
  
  return NextResponse.json(
    {
      status: "ok",
      service: "vapi",
      ts,
    },
    { status: 200 }
  );
}
