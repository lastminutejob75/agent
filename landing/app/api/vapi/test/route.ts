import { NextResponse } from "next/server";

/**
 * GET /api/vapi/test
 * Returns example payload and response for testing
 */
export async function GET() {
  const examplePayload = {
    message: {
      type: "user-message",
      content: "Je veux un rendez-vous",
    },
    call: {
      id: "test_call_123",
      from: "+33123456789",
    },
  };
  
  const exampleResponse = {
    say: "Très bien. Pour commencer, quel est votre nom et prénom ?",
    text: "Très bien. Pour commencer, quel est votre nom et prénom ?",
    endCall: false,
  };
  
  return NextResponse.json(
    {
      message: "Vapi test endpoint",
      example: {
        payload: examplePayload,
        response: exampleResponse,
      },
      modes: {
        simple: "Returns { say, text, endCall }",
        tool: "Returns { say, text, endCall, data }",
      },
      currentMode: process.env.VAPI_MODE || "simple",
    },
    { status: 200 }
  );
}
