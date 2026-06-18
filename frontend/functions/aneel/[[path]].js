// Proxy same-origin para a API de dados abertos da ANEEL.
// A ANEEL não envia cabeçalhos CORS; este Function (Cloudflare Pages) faz a
// requisição no servidor e devolve o JSON na mesma origem do site.
// Ex.: /aneel/api/3/action/datastore_search?... → dadosabertos.aneel.gov.br/...
export async function onRequest(context) {
  const { request, params } = context;
  const url = new URL(request.url);
  const caminho = Array.isArray(params.path) ? params.path.join("/") : (params.path || "");
  const alvo = `https://dadosabertos.aneel.gov.br/${caminho}${url.search}`;

  const resp = await fetch(alvo, { headers: { Accept: "application/json" } });
  const corpo = await resp.text();
  return new Response(corpo, {
    status: resp.status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=86400",
    },
  });
}
