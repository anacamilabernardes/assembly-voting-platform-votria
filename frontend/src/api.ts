export async function api(path: string, body?: unknown): Promise<any> {
  const key = crypto.randomUUID();
  const csrf = document.cookie.split('; ').find(s => s.startsWith('csrftoken='))?.split('=')[1] || '';
  const options: RequestInit = {credentials: 'same-origin', headers: body === undefined ? {} : {'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(csrf),'Idempotency-Key':key}, method: body === undefined ? 'GET' : 'POST', ...(body === undefined ? {} : {body:JSON.stringify(body)})};
  let response: Response;
  try { response = await fetch('/api/v1'+path, options); }
  catch { response = await fetch('/api/v1'+path, options); }
  if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('O servidor não aceitou a solicitação. Atualize a página e tente novamente.');
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir a operação.');
  return data;
}
