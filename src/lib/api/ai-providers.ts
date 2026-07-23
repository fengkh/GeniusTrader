import { apiRequest } from "@/lib/api/client";
import type {
  AIProvider,
  AIProviderPayload,
  AIProviderTestResult,
  ApiMessage,
  UUID
} from "@/lib/api/types";

export async function listAIProviders(): Promise<AIProvider[]> {
  return apiRequest<AIProvider[]>("/ai/providers");
}

export async function createAIProvider(payload: AIProviderPayload): Promise<AIProvider> {
  return apiRequest<AIProvider>("/ai/providers", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateAIProvider(
  providerId: UUID,
  payload: Partial<AIProviderPayload>
): Promise<AIProvider> {
  return apiRequest<AIProvider>(`/ai/providers/${providerId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function deleteAIProvider(providerId: UUID): Promise<ApiMessage> {
  return apiRequest<ApiMessage>(`/ai/providers/${providerId}`, {
    method: "DELETE"
  });
}

export async function testAIProvider(providerId: UUID): Promise<AIProviderTestResult> {
  return apiRequest<AIProviderTestResult>(`/ai/providers/${providerId}/test`, {
    method: "POST"
  });
}
