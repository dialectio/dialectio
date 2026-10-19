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

/** Where "Sign in with Google" starts; the member comes back to `next` (a path without the locale). */
export const googleSignInUrl = (locale: string, next: string) =>
  `${API_URL}/api/auth/google/start?${new URLSearchParams({ locale, next })}`;

const MEMBER_KEY = "dialectio.member";

export async function fetchMe() {
  const member = await call<Member | null>("/me", "GET");
  // Signed in or out on another page (Google sign-in comes back with a page load):
  // the quizzes remembered here belonged to whoever used this browser before
  try {
    const who = member ? String(member.id) : "guest";
    if (localStorage.getItem(MEMBER_KEY) !== who) {
      forgetQuizzes();
      localStorage.setItem(MEMBER_KEY, who);
    }
  } catch {
    // no storage: nothing remembered either
  }
  return member;
}

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
