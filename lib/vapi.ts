/**
 * Vapi integration utilities
 * Parse payloads, build responses, handle conversation turns
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
}

export interface VapiTurnResult {
  action: "say" | "transfer";
  text?: string;
  reason?: string;
}

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
 * Handle a Vapi conversation turn
 * V1: Simple logic for medical appointments
 */
export function handleVapiTurn(inputText: string): VapiTurnResult {
  const text = inputText.trim().toLowerCase();
  
  // Input vide
  if (!text || text.length === 0) {
    return {
      action: "say",
      text: "Je n'ai pas bien entendu. Pouvez-vous répéter ?",
    };
  }
  
  // Détection intent RDV
  const rdvKeywords = [
    "rdv",
    "rendez-vous",
    "rendez vous",
    "rendezvous",
    "disponible",
    "disponibilité",
    "créneau",
    "créneaux",
    "prendre rendez",
    "vouloir rendez",
    "besoin rendez",
    "appointment",
  ];
  
  const hasRdvIntent = rdvKeywords.some(keyword => text.includes(keyword));
  
  if (hasRdvIntent) {
    return {
      action: "say",
      text: "Très bien. Pour commencer, quel est votre nom et prénom ?",
    };
  }
  
  // Hors scope : prix, conseils médicaux, symptômes
  const outOfScopeKeywords = [
    "prix",
    "tarif",
    "coût",
    "combien",
    "payer",
    "conseil",
    "symptôme",
    "symptomes",
    "douleur",
    "mal",
    "maladie",
    "traitement",
    "médicament",
    "ordonnance",
  ];
  
  const isOutOfScope = outOfScopeKeywords.some(keyword => text.includes(keyword));
  
  if (isOutOfScope) {
    return {
      action: "transfer",
      reason: "hors_scope",
    };
  }
  
  // Par défaut : question de clarification
  return {
    action: "say",
    text: "Je peux vous aider à prendre un rendez-vous. Souhaitez-vous réserver un créneau ?",
  };
}
