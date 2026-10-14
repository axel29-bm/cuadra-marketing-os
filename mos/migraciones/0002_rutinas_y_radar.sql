-- Marketing OS · versión 2: lectura automática del radar y registro de rutinas (Fase 4)
-- Solo expande: agrega una columna y dos tablas. Nada se renombra ni se borra.

-- Palabras que debe contener un enlace nuevo para entrar al radar (JSON). Vacío = todos.
ALTER TABLE fuente ADD COLUMN filtro TEXT NOT NULL DEFAULT '[]';

-- Lo que el lector vio la última vez en cada fuente, para detectar solo lo nuevo.
CREATE TABLE fuente_estado (
  fuente_id INTEGER PRIMARY KEY REFERENCES fuente(id),
  enlaces TEXT NOT NULL DEFAULT '[]',          -- enlaces vistos (JSON), como mucho los últimos 3000
  huella TEXT,                                 -- SHA-256 del último contenido leído
  lecturas INTEGER NOT NULL DEFAULT 0,
  actualizado_en TEXT NOT NULL
) STRICT;

-- Cada pasada de una rutina: sirve para comprobar que la tarea programada de verdad corrió.
CREATE TABLE rutina (
  id INTEGER PRIMARY KEY,
  tipo TEXT NOT NULL CHECK (tipo IN ('DIARIA','SEMANAL')),
  fecha TEXT NOT NULL,                         -- día de Lima al que corresponde
  iniciada_en TEXT NOT NULL,
  terminada_en TEXT,
  estado TEXT NOT NULL DEFAULT 'EN_CURSO' CHECK (estado IN ('EN_CURSO','OK','CON_FALLOS')),
  informe TEXT,                                -- ruta del informe, relativa al espacio
  detalle TEXT NOT NULL DEFAULT '{}',          -- resultado de cada paso (JSON)
  CHECK (estado = 'EN_CURSO' OR terminada_en IS NOT NULL)
) STRICT;

CREATE INDEX rutina_por_tipo ON rutina (tipo, iniciada_en);
