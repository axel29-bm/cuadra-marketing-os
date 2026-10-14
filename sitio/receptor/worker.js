// Receptor del formulario de la lista de espera, para Cloudflare Workers con una base D1.
//
// POST /api/lista            guarda una inscripción (solo con consentimiento) y responde {ok} o {ok: false, codigo}
// GET  /api/lista/exportar   CSV de inscripciones para la base local de Didi (requiere la clave)
// POST /api/lista/borrar     borra del servidor las inscripciones ya importadas (requiere la clave)
//
// Mismas reglas que mos/sitio.py (validar_envio). No guarda la IP: guarda su huella SHA-256 con una sal secreta,
// para limitar envíos y como parte de la prueba del consentimiento. Secretos con `wrangler secret put`, nunca aquí.

const RE_EMAIL = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;
const MAX_CUERPO = 10000;
const MAX_POR_HORA = 5;

function respuesta(cuerpo, estado, env, extra = {}) {
  return new Response(cuerpo === null ? null : typeof cuerpo === "string" ? cuerpo : JSON.stringify(cuerpo), {
    status: estado,
    headers: {
      "Content-Type": typeof cuerpo === "string" ? "text/csv; charset=utf-8" : "application/json",
      "Access-Control-Allow-Origin": env.ORIGEN || "null",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      Vary: "Origin",
      ...extra,
    },
  });
}

export function validarEnvio(cuerpo) {
  if (!cuerpo || typeof cuerpo !== "object" || Array.isArray(cuerpo)) return ["DATOS_INCOMPLETOS", null];
  if (String(cuerpo.sitio_web || "").trim()) return ["TRAMPA", null];
  const texto = (k, n) => String(cuerpo[k] ?? "").trim().slice(0, n);
  const nombre = texto("nombre", 80);
  const email = texto("email", 120).toLowerCase();
  if (!nombre || !email) return ["DATOS_INCOMPLETOS", null];
  if (!RE_EMAIL.test(email)) return ["CORREO_INVALIDO", null];
  if (cuerpo.consentimiento !== true) return ["SIN_CONSENTIMIENTO", null];
  const version = texto("aviso_version", 40);
  if (!version) return ["DATOS_INCOMPLETOS", null];
  const empresas = texto("empresas", 6);
  const n = /^\d+$/.test(empresas) ? Number(empresas) : NaN;
  const origenEntrada = cuerpo.origen && typeof cuerpo.origen === "object" && !Array.isArray(cuerpo.origen) ? cuerpo.origen : {};
  const origen = Object.fromEntries(Object.entries(origenEntrada).slice(0, 6).map(([k, v]) => [String(k).slice(0, 30), String(v).slice(0, 200)]));
  return [null, {
    nombre, email, empresas: n >= 1 && n <= 5000 ? n : null, problema: texto("problema", 500),
    demo: cuerpo.demo === true, publicidad: cuerpo.publicidad === true, aviso_version: version, origen,
  }];
}

async function huella(texto) {
  const datos = new TextEncoder().encode(texto);
  const resumen = await crypto.subtle.digest("SHA-256", datos);
  return [...new Uint8Array(resumen)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function autorizado(request, env) {
  const esperado = `Bearer ${env.CLAVE_EXPORTAR || ""}`;
  const recibido = request.headers.get("Authorization") || "";
  if (!env.CLAVE_EXPORTAR || env.CLAVE_EXPORTAR.length < 24 || recibido.length !== esperado.length) return false;
  let distinto = 0;
  for (let i = 0; i < esperado.length; i++) distinto |= esperado.charCodeAt(i) ^ recibido.charCodeAt(i);
  return distinto === 0;
}

function celda(valor) {
  const s = valor === null || valor === undefined ? "" : String(valor);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

async function inscribir(request, env, ahora) {
  if (!env.SAL || env.SAL.length < 16) return respuesta({ ok: false, codigo: "ERROR" }, 500, env);
  const texto = await request.text();
  if (texto.length > MAX_CUERPO) return respuesta({ ok: false, codigo: "ERROR" }, 413, env);
  let cuerpo;
  try { cuerpo = JSON.parse(texto); } catch { cuerpo = null; }
  const [codigo, ins] = validarEnvio(cuerpo);
  if (codigo === "TRAMPA") return respuesta({ ok: true }, 200, env);
  if (codigo) return respuesta({ ok: false, codigo }, 400, env);
  const ip = request.headers.get("CF-Connecting-IP") || "";
  const ipHuella = await huella(`${env.SAL}|${ip}`);
  const haceUnaHora = new Date(ahora.getTime() - 3600 * 1000).toISOString();
  const recientes = await env.DB.prepare("SELECT COUNT(*) AS n FROM inscripcion WHERE ip_hash = ? AND actualizado_en > ?")
    .bind(ipHuella, haceUnaHora).first();
  if (recientes && recientes.n >= MAX_POR_HORA) return respuesta({ ok: false, codigo: "DEMASIADOS_ENVIOS" }, 429, env);
  const marca = ahora.toISOString();
  await env.DB.prepare(
    `INSERT INTO inscripcion (email, nombre, problema, empresas, consentimiento, publicidad, demo, aviso_version, origen, ip_hash, creado_en, actualizado_en)
     VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(email) DO UPDATE SET nombre = excluded.nombre, problema = excluded.problema, empresas = excluded.empresas,
       publicidad = excluded.publicidad, demo = MAX(demo, excluded.demo), aviso_version = excluded.aviso_version,
       origen = excluded.origen, ip_hash = excluded.ip_hash, actualizado_en = excluded.actualizado_en`)
    .bind(ins.email, ins.nombre, ins.problema, ins.empresas, ins.publicidad ? 1 : 0, ins.demo ? 1 : 0, ins.aviso_version,
      JSON.stringify(ins.origen), ipHuella, marca, marca)
    .run();
  return respuesta({ ok: true }, 200, env);
}

async function exportar(env) {
  const { results } = await env.DB.prepare(
    "SELECT email, nombre, problema, empresas, consentimiento, publicidad, demo, aviso_version, origen, creado_en FROM inscripcion ORDER BY id").all();
  const columnas = ["email", "nombre", "problema", "empresas", "consentimiento", "publicidad", "demo", "aviso_version", "origen", "creado_en"];
  const lineas = [columnas.join(",")].concat((results || []).map((f) => columnas.map((c) => celda(f[c])).join(",")));
  return respuesta(lineas.join("\r\n") + "\r\n", 200, env);
}

async function borrar(request, env) {
  let cuerpo;
  try { cuerpo = await request.json(); } catch { cuerpo = null; }
  const correos = Array.isArray(cuerpo?.emails) ? cuerpo.emails.filter((e) => typeof e === "string").slice(0, 500) : [];
  let borrados = 0;
  for (const email of correos) {
    const r = await env.DB.prepare("DELETE FROM inscripcion WHERE email = ?").bind(email.trim().toLowerCase()).run();
    borrados += r?.meta?.changes || 0;
  }
  return respuesta({ ok: true, borrados }, 200, env);
}

export default {
  async fetch(request, env, _ctx, ahora = new Date()) {
    const { pathname } = new URL(request.url);
    if (request.method === "OPTIONS") return respuesta(null, 204, env);
    try {
      if (pathname === "/api/lista" && request.method === "POST") return await inscribir(request, env, ahora);
      if (pathname === "/api/lista/exportar" && request.method === "GET") {
        return autorizado(request, env) ? await exportar(env) : respuesta({ ok: false }, 401, env);
      }
      if (pathname === "/api/lista/borrar" && request.method === "POST") {
        return autorizado(request, env) ? await borrar(request, env) : respuesta({ ok: false }, 401, env);
      }
      return respuesta({ ok: false }, 404, env);
    } catch (e) {
      console.error("receptor", e && e.message);   // sin datos de la persona en el registro
      return respuesta({ ok: false, codigo: "ERROR" }, 500, env);
    }
  },
};
