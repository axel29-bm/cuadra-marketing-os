// Pruebas del receptor con una D1 simulada sobre node:sqlite. Ejecutar: node --test sitio/receptor/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import receptor, { validarEnvio } from "./worker.js";

const ESQUEMA = readFileSync(new URL("./schema.sql", import.meta.url), "utf8");

// Lo mínimo de la API de D1 que usa el receptor: prepare().bind().first()/all()/run().
function d1() {
  const db = new DatabaseSync(":memory:");
  db.exec(ESQUEMA);
  return {
    db,
    prepare(sql) {
      const st = db.prepare(sql);
      const hecho = (args) => ({
        first: async () => st.get(...args) ?? null,
        all: async () => ({ results: st.all(...args) }),
        run: async () => ({ success: true, meta: { changes: Number(st.run(...args).changes) } }),
      });
      return { bind: (...args) => hecho(args), ...hecho([]) };
    },
  };
}

const ENV = () => ({ DB: d1(), SAL: "sal-de-prueba-larga-123456", CLAVE_EXPORTAR: "clave-de-prueba-larga-1234567890", ORIGEN: "https://ejemplo.pages.dev" });
const BUENO = { nombre: "Contadora de Prueba", email: "Prueba@Example.com", empresas: "35", problema: "El SIRE", consentimiento: true,
  publicidad: false, demo: true, aviso_version: "2026-10-14", origen: { utm_source: "facebook" }, sitio_web: "" };
const AHORA = new Date("2026-10-20T15:00:00Z");

function pedir(ruta, { metodo = "POST", cuerpo, clave, ip = "203.0.113.7" } = {}) {
  const headers = { "Content-Type": "application/json", "CF-Connecting-IP": ip };
  if (clave) headers.Authorization = `Bearer ${clave}`;
  return new Request(`https://receptor.example${ruta}`, { method: metodo, headers, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) });
}

test("sin consentimiento no se guarda nada", async () => {
  const env = ENV();
  const r = await receptor.fetch(pedir("/api/lista", { cuerpo: { ...BUENO, consentimiento: false } }), env, null, AHORA);
  assert.equal(r.status, 400);
  assert.deepEqual(await r.json(), { ok: false, codigo: "SIN_CONSENTIMIENTO" });
  assert.equal(env.DB.db.prepare("SELECT COUNT(*) AS n FROM inscripcion").get().n, 0);
});

test("una inscripción válida se guarda una sola vez, sin la IP", async () => {
  const env = ENV();
  for (let i = 0; i < 2; i++) {
    const r = await receptor.fetch(pedir("/api/lista", { cuerpo: BUENO }), env, null, AHORA);
    assert.deepEqual(await r.json(), { ok: true });
  }
  const filas = env.DB.db.prepare("SELECT * FROM inscripcion").all();
  assert.equal(filas.length, 1);
  assert.equal(filas[0].email, "prueba@example.com");
  assert.equal(filas[0].empresas, 35);
  assert.equal(filas[0].demo, 1);
  assert.equal(filas[0].aviso_version, "2026-10-14");
  assert.equal(filas[0].ip_hash.length, 64);
  assert.ok(!JSON.stringify(filas[0]).includes("203.0.113.7"));
});

test("un robot que llena el campo oculto recibe ok y no se guarda", async () => {
  const env = ENV();
  const r = await receptor.fetch(pedir("/api/lista", { cuerpo: { ...BUENO, sitio_web: "http://spam" } }), env, null, AHORA);
  assert.deepEqual(await r.json(), { ok: true });
  assert.equal(env.DB.db.prepare("SELECT COUNT(*) AS n FROM inscripcion").get().n, 0);
});

test("más de cinco envíos por hora desde la misma conexión se frenan", async () => {
  const env = ENV();
  for (let i = 0; i < 5; i++) {
    const r = await receptor.fetch(pedir("/api/lista", { cuerpo: { ...BUENO, email: `p${i}@example.com` } }), env, null, AHORA);
    assert.equal(r.status, 200);
  }
  const r = await receptor.fetch(pedir("/api/lista", { cuerpo: { ...BUENO, email: "p9@example.com" } }), env, null, AHORA);
  assert.equal(r.status, 429);
  const otra = await receptor.fetch(pedir("/api/lista", { cuerpo: { ...BUENO, email: "p9@example.com" }, ip: "198.51.100.2" }), env, null, AHORA);
  assert.equal(otra.status, 200);
});

test("exportar y borrar exigen la clave", async () => {
  const env = ENV();
  await receptor.fetch(pedir("/api/lista", { cuerpo: BUENO }), env, null, AHORA);
  assert.equal((await receptor.fetch(pedir("/api/lista/exportar", { metodo: "GET" }), env)).status, 401);
  assert.equal((await receptor.fetch(pedir("/api/lista/exportar", { metodo: "GET", clave: "otra" }), env)).status, 401);
  const csv = await (await receptor.fetch(pedir("/api/lista/exportar", { metodo: "GET", clave: env.CLAVE_EXPORTAR }), env)).text();
  assert.match(csv, /^email,nombre,problema,empresas,consentimiento,publicidad,demo,aviso_version,origen,creado_en\r\n/);
  assert.match(csv, /prueba@example\.com,Contadora de Prueba,El SIRE,35,1,0,1,2026-10-14,"{""utm_source"":""facebook""}",2026-10-20T15:00:00\.000Z/);
  assert.equal((await receptor.fetch(pedir("/api/lista/borrar", { cuerpo: { emails: ["prueba@example.com"] } }), env)).status, 401);
  const b = await receptor.fetch(pedir("/api/lista/borrar", { cuerpo: { emails: ["prueba@example.com"] }, clave: env.CLAVE_EXPORTAR }), env);
  assert.deepEqual(await b.json(), { ok: true, borrados: 1 });
  assert.equal(env.DB.db.prepare("SELECT COUNT(*) AS n FROM inscripcion").get().n, 0);
});

test("sin sal configurada no recibe nada", async () => {
  const env = { ...ENV(), SAL: "" };
  const r = await receptor.fetch(pedir("/api/lista", { cuerpo: BUENO }), env, null, AHORA);
  assert.equal(r.status, 500);
});

test("las reglas de validación coinciden con las de mos/sitio.py", () => {
  assert.equal(validarEnvio(null)[0], "DATOS_INCOMPLETOS");
  assert.equal(validarEnvio({ ...BUENO, email: "sin-arroba" })[0], "CORREO_INVALIDO");
  assert.equal(validarEnvio({ ...BUENO, consentimiento: "true" })[0], "SIN_CONSENTIMIENTO");
  assert.equal(validarEnvio({ ...BUENO, aviso_version: "" })[0], "DATOS_INCOMPLETOS");
  assert.equal(validarEnvio({ ...BUENO, empresas: "9999" })[1].empresas, null);
  assert.equal(validarEnvio({ ...BUENO, nombre: "x".repeat(200) })[1].nombre.length, 80);
});
