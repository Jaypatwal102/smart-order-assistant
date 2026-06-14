const API_URL = "http://localhost:8000";

export async function loginUser(email: string, password: string) {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Login failed");
  }

  const data = await response.json();
  // Set the token as a cookie so middleware can read it
  document.cookie = `token=${data.access_token}; path=/; max-age=2592000; SameSite=Lax`;
  return data;
}

export async function registerUser(firstName: string, lastName: string, email: string, password: string) {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ first_name: firstName, last_name: lastName, email, password }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Registration failed");
  }

  return response.json();
}

export async function getCurrentUser(token: string) {
  const response = await fetch(`${API_URL}/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch user");
  }

  return response.json();
}

export function logoutUser() {
  document.cookie = "token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
}

export async function sendMessage(token: string, text: string, conversationId: string | null = null) {
  const body: any = { message_text: text };
  if (conversationId) {
    body.conversation_id = conversationId;
  }
  
  const response = await fetch(`${API_URL}/conversations/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error("Failed to send message");
  }

  return response.json();
}
