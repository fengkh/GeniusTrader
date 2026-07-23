import { apiRequest } from "@/lib/api/client";
import type { ApiMessage, AuthUserResponse, LoginResponse } from "@/lib/api/types";

export async function login(username: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
    redirectOnUnauthorized: false
  });
}

export async function getCurrentUser(): Promise<AuthUserResponse> {
  return apiRequest<AuthUserResponse>("/auth/me", {
    redirectOnUnauthorized: false
  });
}

export async function logout(): Promise<ApiMessage> {
  return apiRequest<ApiMessage>("/auth/logout", {
    method: "POST",
    redirectOnUnauthorized: false
  });
}
