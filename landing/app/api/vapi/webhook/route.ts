import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";
import {
  parseVapiPayload,
  buildVapiResponseSay,
  buildVapiResponseTransfer,
  buildVapiResponseTool,
  buildVapiResponseResults,
  handleVapiTurn,
} from "@/lib/vapi";

const VAPI_MODE = process.env.VAPI_MODE || "simple";
const MAX_HANDLER_MS = 800;

/**
 * POST /api/vapi/webhook
 * Main webhook endpoint for Vapi
 */
export async function POST(request: NextRequest) {
  const requestId = randomUUID();
  const startTime = Date.now();
  
  try {
    // Parse request body
    const body = await request.json();
    
    // Log request
    console.log(`[${requestId}] Vapi webhook received`, {
      callId: body?.call?.id,
      messageType: body?.message?.type,
      timestamp: new Date().toISOString(),
    });
    
    // Parse Vapi payload
    const { inputText, callId, fromNumber, raw } = parseVapiPayload(body);
    
    console.log(`[${requestId}] Parsed payload`, {
      callId,
      fromNumber,
      inputText: inputText.substring(0, 100), // Limit log length
    });
    
    // Handle conversation turn with timeout protection
    const handlerStart = Date.now();
    let turnResult;
    
    try {
      turnResult = handleVapiTurn(inputText, callId);
    } catch (error) {
      console.error(`[${requestId}] Error in handleVapiTurn:`, error);
      turnResult = {
        action: "transfer",
        reason: "internal_error",
      };
    }
    
    const handlerDuration = Date.now() - handlerStart;
    
    // Timeout soft: si > 800ms, transfert
    if (handlerDuration > MAX_HANDLER_MS) {
      console.warn(`[${requestId}] Handler timeout (${handlerDuration}ms), transferring`);
      turnResult = {
        action: "transfer",
        reason: "timeout",
      };
    }
    
    // Build response based on mode
    let response;
    if (turnResult.action === "transfer") {
      response = buildVapiResponseTransfer(turnResult.reason);
    } else if (VAPI_MODE === "results") {
      // Format compatible FastAPI (results array)
      response = buildVapiResponseResults(turnResult.text || "");
    } else if (VAPI_MODE === "tool") {
      response = buildVapiResponseTool(turnResult.text || "", {
        confidence: 1.0,
      });
    } else {
      // Mode simple (par défaut)
      response = buildVapiResponseSay(turnResult.text || "");
    }
    
    const totalDuration = Date.now() - startTime;
    
    // Log response
    console.log(`[${requestId}] Response sent`, {
      callId,
      action: turnResult.action,
      duration_ms: totalDuration,
      handler_ms: handlerDuration,
    });
    
    // Return JSON response
    return NextResponse.json(response, {
      status: 200,
      headers: {
        "Content-Type": "application/json",
      },
    });
    
  } catch (error) {
    const duration = Date.now() - startTime;
    console.error(`[${requestId}] Webhook error:`, error);
    
    // En cas d'erreur : status 200 + message d'excuse (pour éviter silence)
    const errorResponse = buildVapiResponseSay(
      "Désolé, une erreur s'est produite. Je vous transfère à un humain."
    );
    
    if (VAPI_MODE === "tool") {
      errorResponse.data = {
        action: "error",
        error: "internal_error",
      };
    }
    
    return NextResponse.json(errorResponse, {
      status: 200,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }
}
