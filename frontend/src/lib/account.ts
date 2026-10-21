import { API_URL } from "@/lib/api";
import { forgetQuizzes } from "@/lib/feedback";

/** A signed-in member (the session is an HttpOnly cookie the API sets). */
export type Member = {
  id: number;
  email: string;
  name: string;
  role: string;
  /** Proven with an emailed link or Google */
  email_verified: boolean;
};

/** The API's reason for a refused sign-up or sign-in ("email_taken", "wrong_credentials" ...). */
export class AccountError extends Error {}

/** A JSON request to the API with the session cookie; errors carry the API's reason. */
export async function apiCall<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
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

const call = <T>(path: string, method: string, body?: unknown) =>
  apiCall<T>(`/api/auth${path}`, method, body);

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
  /** Language of the confirmation email */
  locale: string;
  /** Turnstile token (components/Captcha.tsx) */
  captcha: string;
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

// --- Emailed links ------------------------------------------------------------------------

const NEXT_KEY = "dialectio.afterLink";

/** Where to go after following a sign-in link (the link opens a page of its own). */
export function rememberNext(path: string) {
  try {
    localStorage.setItem(NEXT_KEY, path);
  } catch {
    // the member lands on the home page instead
  }
}

export function takeNext(): string {
  try {
    const next = localStorage.getItem(NEXT_KEY) ?? "/";
    localStorage.removeItem(NEXT_KEY);
    return next.startsWith("/") && !next.startsWith("//") ? next : "/";
  } catch {
    return "/";
  }
}

export const sendLoginLink = (email: string, locale: string, captcha: string) =>
  call<null>("/email/login-link", "POST", { email, locale, captcha });

export const forgotPassword = (
  email: string,
  locale: string,
  captcha: string,
) => call<null>("/password/forgot", "POST", { email, locale, captcha });

export const resendVerification = (locale: string) =>
  call<null>("/email/verification", "POST", { locale });

export const verifyEmail = (token: string) =>
  call<Member>("/email/verify", "POST", { token });

export async function signInWithLink(token: string) {
  const member = await call<Member>("/email/login", "POST", { token });
  forgetQuizzes();
  return member;
}

export async function resetPassword(token: string, password: string) {
  const member = await call<Member>("/password/reset", "POST", {
    token,
    password,
  });
  forgetQuizzes();
  return member;
}
