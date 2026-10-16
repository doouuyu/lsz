import { createConsultation } from "@/api";

export interface ConsultationCredentials {
  id: string;
  token: string;
  role: string;
}

let current: ConsultationCredentials | null = null;
let creating: Promise<ConsultationCredentials> | null = null;

export function getConsultationSession() {
  return current;
}

export function clearConsultationSession() {
  current = null;
  creating = null;
}

export function ensureConsultationSession(role: string): Promise<ConsultationCredentials> {
  if (current && current.role === role) return Promise.resolve(current);
  if (creating) return creating;
  creating = createConsultation(role).then((session) => {
    current = {
      id: session.consultation_id,
      token: session.consultation_token,
      role,
    };
    creating = null;
    return current;
  });
  return creating;
}
