-- Marketing OS · versión 4: la rutina admite la revisión MENSUAL (Fase 6)
--
-- SQLite no cambia un CHECK en su sitio: se rehace la tabla con los mismos
-- datos (ninguna otra tabla apunta a ella).
CREATE TABLE rutina_v4 (
  id INTEGER PRIMARY KEY,
  tipo TEXT NOT NULL CHECK (tipo IN ('DIARIA','SEMANAL','MENSUAL')),
  fecha TEXT NOT NULL,                         -- día de Lima al que corresponde
  iniciada_en TEXT NOT NULL,
  terminada_en TEXT,
  estado TEXT NOT NULL DEFAULT 'EN_CURSO' CHECK (estado IN ('EN_CURSO','OK','CON_FALLOS')),
  informe TEXT,                                -- ruta del informe, relativa al espacio
  detalle TEXT NOT NULL DEFAULT '{}',          -- resultado de cada paso (JSON)
  CHECK (estado = 'EN_CURSO' OR terminada_en IS NOT NULL)
) STRICT;
INSERT INTO rutina_v4 (id, tipo, fecha, iniciada_en, terminada_en, estado, informe, detalle)
  SELECT id, tipo, fecha, iniciada_en, terminada_en, estado, informe, detalle FROM rutina;
DROP TABLE rutina;
ALTER TABLE rutina_v4 RENAME TO rutina;
CREATE INDEX rutina_por_tipo ON rutina (tipo, iniciada_en);
