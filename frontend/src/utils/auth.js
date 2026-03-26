/**
 * Token and user session utilities.
 * All auth state lives in localStorage — JWT is stateless.
 */

export const getToken = () => localStorage.getItem("token");

export const getUser = () => {
  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const setAuth = (token, user) => {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
};

export const clearAuth = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
};

export const isAuthenticated = () => !!getToken();

/**
 * Attempt to detect the carrier from a tracking number's format.
 * Returns a carrier code or null if undetectable.
 */
export const detectCarrier = (trackingNumber) => {
  const tn = trackingNumber.trim().toUpperCase();
  if (/^1Z[A-Z0-9]{16}$/.test(tn)) return "UPS";
  if (/^\d{12}$/.test(tn) || /^\d{15}$/.test(tn) || /^\d{20}$/.test(tn)) return "FEDEX";
  return null;
};
