const env = (import.meta as ImportMeta & {env:Record<string,string>}).env;
const base = (env.VITE_API_URL || '').replace(/\/$/, '');
export async function api<T>(path:string, options:RequestInit = {}):Promise<T> {
  const controller = new AbortController(); const timer = setTimeout(()=>controller.abort(),60000);
  try {
    const response = await fetch(`${base}/api${path}`, {...options,signal:controller.signal});
    const data = await response.json().catch(()=>null);
    if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status}): ${JSON.stringify(data?.detail || response.statusText)}`);
    return data as T;
  } catch(error) {if(error instanceof DOMException && error.name==='AbortError') throw new Error('The request timed out. Check the backend and retry.'); throw error;}
  finally {clearTimeout(timer);}
}
