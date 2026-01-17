/**
 * Vapi integration utilities
 * Parse payloads, build responses, handle conversation turns
 * FSM ultra-simplifiée pour prise de RDV vocal
 */

export interface VapiPayload {
  message?: {
    type?: string;
    content?: string;
    text?: string;
  };
  call?: {
    id?: string;
    from?: string;
  };
  [key: string]: any;
}

export interface ParsedVapiPayload {
  inputText: string;
  callId: string;
  fromNumber?: string;
  raw: VapiPayload;
}

export interface VapiResponse {
  say?: string;
  text?: string;
  endCall?: boolean;
  data?: any;
  results?: Array<{
    type: string;
    text: string;
  }>;
}

export interface VapiTurnResult {
  action: "say" | "transfer";
  text?: string;
  reason?: string;
}

// Session store en mémoire (suffisant pour Vapi)
interface Session {
  state: string;
  data: {
    name?: string;
    motif?: string;
    contact?: string;
  };
}

const SESSIONS: Record<string, Session> = {};

/**
 * Parse Vapi webhook payload
 */
export function parseVapiPayload(body: any): ParsedVapiPayload {
  const payload = body as VapiPayload;
  
  // Extraire le texte utilisateur
  let inputText = "";
  if (payload.message?.content) {
    inputText = payload.message.content;
  } else if (payload.message?.text) {
    inputText = payload.message.text;
  } else if (typeof payload.message === "string") {
    inputText = payload.message;
  } else if (typeof body === "string") {
    inputText = body;
  }
  
  // Extraire call ID
  const callId = payload.call?.id || `call_${Date.now()}`;
  
  // Extraire numéro appelant
  const fromNumber = payload.call?.from;
  
  return {
    inputText: inputText.trim(),
    callId,
    fromNumber,
    raw: payload,
  };
}

/**
 * Build Vapi response in "simple" mode
 */
export function buildVapiResponseSay(text: string): VapiResponse {
  return {
    say: text,
    text: text,
    endCall: false,
  };
}

/**
 * Build Vapi response for transfer
 */
export function buildVapiResponseTransfer(reason?: string): VapiResponse {
  const message = reason 
    ? `Je vous transfère à un humain. ${reason}`
    : "Je vous transfère à un humain pour vous aider.";
  
  return {
    say: message,
    text: message,
    endCall: false,
    data: {
      action: "transfer",
      reason: reason || "out_of_scope",
    },
  };
}

/**
 * Build Vapi response in "tool" mode
 */
export function buildVapiResponseTool(text: string, data?: any): VapiResponse {
  return {
    say: text,
    text: text,
    endCall: false,
    data: {
      action: "say",
      confidence: 1.0,
      ...data,
    },
  };
}

/**
 * Build Vapi response in "results" format (compatible FastAPI)
 */
export function buildVapiResponseResults(text: string): VapiResponse {
  return {
    results: [{
      type: "say",
      text: text,
    }],
  };
}

/**
 * Handle conversation turn with FSM ultra-simplifiée
 * Logique conversation pour prise de RDV vocal
 */
export function handleVapiTurn(inputText: string, callId: string): VapiTurnResult {
  const text = inputText.trim().toLowerCase();
  
  // Input vide
  if (!text || text.length === 0) {
    return {
      action: "say",
      text: "Je n'ai pas bien entendu. Pouvez-vous répéter ?",
    };
  }
  
  // Récupérer ou créer session
  if (!SESSIONS[callId]) {
    SESSIONS[callId] = {
      state: "START",
      data: {},
    };
  }
  
  const session = SESSIONS[callId];
  
  // FSM ultra-simple
  if (session.state === "START") {
    if (text.includes("rendez-vous") || text.includes("rdv") || text.includes("rendez vous")) {
      session.state = "ASK_NAME";
      return {
        action: "say",
        text: "Quel est votre nom et prénom ?",
      };
    }
    return {
      action: "say",
      text: "Bonjour. Comment puis-je vous aider ?",
    };
  }
  
  else if (session.state === "ASK_NAME") {
    session.data.name = inputText.trim(); // Garder l'original (pas lowercase)
    session.state = "ASK_MOTIF";
    return {
      action: "say",
      text: "Pour quel sujet souhaitez-vous consulter ?",
    };
  }
  
  else if (session.state === "ASK_MOTIF") {
    session.data.motif = inputText.trim();
    session.state = "ASK_CONTACT";
    return {
      action: "say",
      text: "Quel est votre téléphone ou email ?",
    };
  }
  
  else if (session.state === "ASK_CONTACT") {
    session.data.contact = inputText.trim();
    session.state = "PROPOSE_SLOT";
    return {
      action: "say",
      text: "J'ai un créneau Lundi 13 janvier à 10h. Confirmez-vous ?",
    };
  }
  
  else if (session.state === "PROPOSE_SLOT") {
    if (text.includes("oui") || text === "1" || text.includes("confirme")) {
      session.state = "CONFIRMED";
      return {
        action: "say",
        text: "Parfait ! Votre rendez-vous est confirmé. À bientôt.",
      };
    }
    return {
      action: "say",
      text: "Je n'ai pas compris. Dites oui pour confirmer.",
    };
  }
  
  // État CONFIRMED ou inconnu
  if (session.state === "CONFIRMED") {
    return {
      action: "say",
      text: "Votre rendez-vous est déjà confirmé. Y a-t-il autre chose ?",
    };
  }
  
  return {
    action: "say",
    text: "Je n'ai pas compris. Pouvez-vous répéter ?",
  };
}

/**
 * Cleanup old sessions (optionnel, pour éviter fuite mémoire)
 */
export function cleanupOldSessions(maxAgeMs: number = 15 * 60 * 1000) {
  const now = Date.now();
  const toDelete: string[] = [];
  
  for (const [callId, session] of Object.entries(SESSIONS)) {
    // Si session confirmée depuis plus de maxAgeMs, nettoyer
    if (session.state === "CONFIRMED") {
      // Extract timestamp from callId if possible, sinon garder
      // Pour simplifier, on garde toutes les sessions actives
    }
  }
  
  // Pour l'instant, on garde toutes les sessions
  // En production, ajouter un timestamp dans Session
}
