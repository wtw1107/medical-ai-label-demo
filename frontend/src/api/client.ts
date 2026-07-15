import axios, { AxiosError } from "axios";

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;
const apiBaseUrl = configuredApiBaseUrl === undefined ? "http://localhost:8000" : configuredApiBaseUrl;

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: 60000,
});

function formatValidationErrors(validationErrors: unknown) {
  if (!validationErrors || typeof validationErrors !== "object") {
    return null;
  }

  const entries = Object.entries(validationErrors).flatMap(([field, messages]) => {
    if (!Array.isArray(messages)) {
      return [];
    }
    return messages
      .filter((message): message is string => typeof message === "string" && message.length > 0)
      .map((message) => `${field}: ${message}`);
  });

  return entries.length > 0 ? entries.join("; ") : null;
}

function formatFastApiDetail(detail: unknown) {
  if (typeof detail === "string" && detail.length > 0) {
    return detail;
  }

  if (!Array.isArray(detail)) {
    return null;
  }

  const entries = detail.flatMap((item) => {
    if (!item || typeof item !== "object") {
      return [];
    }

    const maybeLoc = "loc" in item ? item.loc : null;
    const maybeMsg = "msg" in item ? item.msg : null;
    const loc = Array.isArray(maybeLoc) ? maybeLoc.join(".") : "request";
    const msg = typeof maybeMsg === "string" ? maybeMsg : null;
    return msg ? [`${loc}: ${msg}`] : [];
  });

  return entries.length > 0 ? entries.join("; ") : null;
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      const responseData = error.response?.data;
      const detailMessage = formatFastApiDetail(responseData?.detail);
      const validationMessage = formatValidationErrors(responseData?.validation_errors);

      if (detailMessage || validationMessage) {
        return Promise.reject(new Error(detailMessage || validationMessage || "Request failed"));
      }

      if (error.code === AxiosError.ERR_NETWORK) {
        return Promise.reject(new Error("Network error: could not reach backend service. Please check backend status and CORS settings."));
      }

      if (error.code === AxiosError.ECONNABORTED) {
        return Promise.reject(new Error("Request timed out. Please retry or reduce the upload size."));
      }
    }

    return Promise.reject(new Error(error instanceof Error ? error.message : "Request failed"));
  },
);

export function buildAbsoluteUrl(path: string) {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  if (!apiBaseUrl) {
    return path;
  }
  return `${apiBaseUrl.replace(/\/$/, "")}${path}`;
}
