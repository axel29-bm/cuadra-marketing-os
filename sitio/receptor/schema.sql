-- Base D1 del receptor: solo lo necesario y solo mientras no se haya importado a la base local de Didi.
-- Crear: npx wrangler d1 execute cuadra-lista --remote --file=schema.sql
CREATE TABLE IF NOT EXISTS inscripcion (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  nombre TEXT NOT NULL DEFAULT '',
  problema TEXT NOT NULL DEFAULT '',
  empresas INTEGER,
  consentimiento INTEGER NOT NULL CHECK (consentimiento = 1),       -- sin consentimiento no se guarda nada
  publicidad INTEGER NOT NULL DEFAULT 0 CHECK (publicidad IN (0, 1)), -- consentimiento aparte para novedades
  demo INTEGER NOT NULL DEFAULT 0 CHECK (demo IN (0, 1)),
  aviso_version TEXT NOT NULL,                                       -- qué texto del aviso aceptó
  origen TEXT NOT NULL DEFAULT '{}',                                 -- utm y referente, en JSON
  ip_hash TEXT NOT NULL,                                             -- SHA-256 de la IP con sal secreta, nunca la IP
  creado_en TEXT NOT NULL,
  actualizado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS inscripcion_ip ON inscripcion (ip_hash, actualizado_en);
