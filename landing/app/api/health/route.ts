import { NextResponse } from "next/server";

/**
 * GET /api/health
 * General health check endpoint
 */
export async function GET() {
  return NextResponse.json(
    {
      status: "ok",
      timestamp: new Date().toISOString(),
    },
    { status: 200 }
  );
}
