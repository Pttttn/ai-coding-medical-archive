export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  let response: Response;
  try { response = await fetch(`/api${path}`, { ...init, headers }); }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new Error('Нет соединения с локальным сервером. Проверьте, запущено ли приложение.');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { message?: string | string[] };
    throw new ApiError(Array.isArray(data.message) ? data.message.join('. ') : data.message || `Сервер вернул ошибку ${response.status}`, response.status);
  }
  if (response.status === 204) return undefined as T;
  if (response.headers.get('Content-Type')?.includes('application/json')) return response.json() as Promise<T>;
  return response.text() as Promise<T>;
}

export const json = (value: unknown) => JSON.stringify(value);
export const message = (error: unknown) => error instanceof Error ? error.message : 'Не удалось выполнить действие.';
export const query = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== '') search.set(key, String(value)); });
  return search.toString();
};
