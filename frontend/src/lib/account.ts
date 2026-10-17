import { API_URL } from "@/lib/api";
import { forgetQuizzes } from "@/lib/feedback";

/** A signed-in member (the session is an HttpOnly cookie the API sets). */
export type Member = { id: number; email: string; name: string; role: string };

/** The API's reason for a refused sign-up or sign-in ("email_taken", "wrong_credentials" ...). */
export class AccountError extends Error {}

async function call<T>(
  path: string,
  method: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_URL}/api/auth${path}`, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new AccountError(
      typeof detail?.detail === "string"
        ? detail.detail
        : String(response.status),
    );
  }
  return (response.status === 204 ? null : await response.json()) as T;
}

export const fetchMe = () => call<Member | null>("/me", "GET");

export async function register(data: {
  email: string;
  password: string;
  name: string;
  website: string;
}) {
  const member = await call<Member>("/register", "POST", data);
  forgetQuizzes(); // the quizzes a guest passed in this browser are not the member's
  return member;
}

export async function signIn(email: string, password: string) {
  const member = await call<Member>("/login", "POST", { email, password });
  forgetQuizzes();
  return member;
}

export async function signOut() {
  await call<null>("/logout", "POST");
  forgetQuizzes();
}

export async function deleteAccount() {
  await call<null>("/me", "DELETE");
  forgetQuizzes();
}
