-- Marketing OS · esquema inicial (versión 1)
-- Convenciones: tablas STRICT en singular y snake_case; fechas AAAA-MM-DD; marcas de tiempo UTC ISO-8601;
-- importes en céntimos (_c); booleanos INTEGER 0/1; listas y objetos como JSON en TEXT.
-- Nada comercial se borra: se archiva, se cancela o se marca. Los leads sí se pueden eliminar a pedido del titular.

CREATE TABLE marca (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  nombre TEXT NOT NULL,
  descripcion TEXT NOT NULL DEFAULT '',
  tokens TEXT NOT NULL DEFAULT '{}',          -- colores, tipografías, radios, espacios
  logo TEXT,                                  -- ruta relativa al repositorio
  provisional INTEGER NOT NULL DEFAULT 1 CHECK (provisional IN (0,1)),
  creado_en TEXT NOT NULL,
  actualizado_en TEXT NOT NULL
) STRICT;

CREATE TABLE producto (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  nombre_provisional TEXT NOT NULL,
  nombre_comercial TEXT,
  sector TEXT NOT NULL,
  publico_objetivo TEXT NOT NULL,
  problemas TEXT NOT NULL DEFAULT '[]',
  propuesta_valor TEXT NOT NULL,
  precio TEXT,
  precio_definido INTEGER NOT NULL DEFAULT 0 CHECK (precio_definido IN (0,1)),
  estado_desarrollo TEXT NOT NULL,
  etapa_comercial TEXT NOT NULL CHECK (etapa_comercial IN
    ('IDEA','DESARROLLO','PRELANZAMIENTO','BETA_PRIVADA','PREVENTA','DISPONIBLE','RETIRADO')),
  disponible_al_publico INTEGER NOT NULL DEFAULT 0 CHECK (disponible_al_publico IN (0,1)),
  validacion_contable TEXT,
  marca_id INTEGER REFERENCES marca(id),
  canales TEXT NOT NULL DEFAULT '[]',
  competidores TEXT NOT NULL DEFAULT '[]',
  presupuesto_mensual_c INTEGER NOT NULL DEFAULT 0 CHECK (presupuesto_mensual_c >= 0),
  repositorio TEXT,
  commit_auditado TEXT,
  fecha_auditoria TEXT,
  notas TEXT NOT NULL DEFAULT '',
  creado_en TEXT NOT NULL,
  actualizado_en TEXT NOT NULL
) STRICT;

CREATE TABLE capacidad (
  id INTEGER PRIMARY KEY,
  producto_id INTEGER NOT NULL REFERENCES producto(id),
  codigo TEXT NOT NULL,
  nombre TEXT NOT NULL,
  estado TEXT NOT NULL CHECK (estado IN
    ('IMPLEMENTADO_VERIFICADO','IMPLEMENTADO_PARCIAL','EN_DESARROLLO','PLANIFICADO','SIN_EVIDENCIA')),
  uso TEXT NOT NULL CHECK (uso IN ('PERMITIDO','CON_MATICES','SOLO_DEMO','NO_ANUNCIAR')),
  evidencia TEXT NOT NULL,
  frase TEXT,
  matiz TEXT,
  prohibido TEXT NOT NULL DEFAULT '[]',
  verificado_en TEXT NOT NULL,
  UNIQUE (producto_id, codigo)
) STRICT;

CREATE TABLE prohibicion (
  id INTEGER PRIMARY KEY,
  producto_id INTEGER REFERENCES producto(id),   -- NULL: aplica a todos los productos
  patron TEXT NOT NULL,
  motivo TEXT NOT NULL,
  UNIQUE (producto_id, patron)
) STRICT;

CREATE TABLE audiencia (
  id INTEGER PRIMARY KEY,
  producto_id INTEGER NOT NULL REFERENCES producto(id),
  slug TEXT NOT NULL,
  nombre TEXT NOT NULL,
  descripcion TEXT NOT NULL,
  dolores TEXT NOT NULL DEFAULT '[]',
  objeciones TEXT NOT NULL DEFAULT '[]',
  canales TEXT NOT NULL DEFAULT '[]',
  naturaleza TEXT NOT NULL DEFAULT 'HIPOTESIS' CHECK (naturaleza IN ('HIPOTESIS','OBSERVADA')),
  UNIQUE (producto_id, slug)
) STRICT;

CREATE TABLE fuente (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  tipo TEXT NOT NULL CHECK (tipo IN ('OFICIAL','REPOSITORIO','COMPETIDOR','MEDIO','HERRAMIENTA','OTRO')),
  organismo TEXT NOT NULL DEFAULT '',
  titulo TEXT NOT NULL,
  url TEXT NOT NULL,
  rss_url TEXT,
  metodo TEXT NOT NULL DEFAULT 'MANUAL' CHECK (metodo IN ('RSS','SITEMAP','HTML','MANUAL')),
  frecuencia_horas INTEGER NOT NULL DEFAULT 24 CHECK (frecuencia_horas >= 6),
  activa INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0,1)),
  ultima_consulta TEXT,
  ultimo_error TEXT,
  notas TEXT NOT NULL DEFAULT ''
) STRICT;

CREATE TABLE radar_item (
  id INTEGER PRIMARY KEY,
  fuente_id INTEGER REFERENCES fuente(id),
  titulo TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  resumen TEXT NOT NULL DEFAULT '',
  fecha_publicacion TEXT,
  fecha_vigencia TEXT,
  afecta_a TEXT NOT NULL DEFAULT '',
  que_cambia TEXT NOT NULL DEFAULT '',
  estado_verificacion TEXT NOT NULL DEFAULT 'SIN_VERIFICAR' CHECK (estado_verificacion IN
    ('SIN_VERIFICAR','VERIFICADA','DESCARTADA','RUMOR')),
  es_fuente_primaria INTEGER NOT NULL DEFAULT 0 CHECK (es_fuente_primaria IN (0,1)),
  requiere_contador INTEGER NOT NULL DEFAULT 1 CHECK (requiere_contador IN (0,1)),
  advertencias TEXT NOT NULL DEFAULT '',
  propuesta_contenido TEXT NOT NULL DEFAULT '',
  verificado_por TEXT,
  verificado_en TEXT,
  detectado_en TEXT NOT NULL,
  CHECK (estado_verificacion <> 'VERIFICADA' OR (es_fuente_primaria = 1 AND verificado_en IS NOT NULL))
) STRICT;

CREATE TABLE campana (
  id INTEGER PRIMARY KEY,
  producto_id INTEGER NOT NULL REFERENCES producto(id),
  slug TEXT NOT NULL UNIQUE,
  nombre TEXT NOT NULL,
  objetivo TEXT NOT NULL,
  audiencia_id INTEGER REFERENCES audiencia(id),
  hipotesis TEXT NOT NULL,
  oferta TEXT NOT NULL,
  cta TEXT NOT NULL,
  metrica_exito TEXT NOT NULL,
  meta_valor INTEGER,
  inicio TEXT,
  fin TEXT,
  presupuesto_c INTEGER NOT NULL DEFAULT 0 CHECK (presupuesto_c >= 0),
  gasto_real_c INTEGER NOT NULL DEFAULT 0 CHECK (gasto_real_c >= 0),
  estado TEXT NOT NULL DEFAULT 'BORRADOR' CHECK (estado IN
    ('BORRADOR','ACTIVA','PAUSADA','TERMINADA','CANCELADA')),
  aprendizaje TEXT NOT NULL DEFAULT '',
  creado_en TEXT NOT NULL,
  actualizado_en TEXT NOT NULL
) STRICT;

CREATE TABLE idea (
  id INTEGER PRIMARY KEY,
  codigo TEXT NOT NULL UNIQUE,
  producto_id INTEGER NOT NULL REFERENCES producto(id),
  campana_id INTEGER REFERENCES campana(id),
  audiencia_id INTEGER REFERENCES audiencia(id),
  problema TEXT NOT NULL,
  idea_central TEXT NOT NULL,
  formato TEXT NOT NULL,
  canal TEXT NOT NULL,
  etapa_embudo TEXT NOT NULL CHECK (etapa_embudo IN
    ('ATENCION','INTERES','CONSIDERACION','CONVERSION','FIDELIZACION')),
  objetivo TEXT NOT NULL,
  relevancia INTEGER NOT NULL CHECK (relevancia BETWEEN 1 AND 5),
  atencion INTEGER NOT NULL CHECK (atencion BETWEEN 1 AND 5),
  valor_comercial INTEGER NOT NULL CHECK (valor_comercial BETWEEN 1 AND 5),
  coste INTEGER NOT NULL CHECK (coste BETWEEN 1 AND 5),
  esfuerzo INTEGER NOT NULL CHECK (esfuerzo BETWEEN 1 AND 5),
  evidencia TEXT NOT NULL DEFAULT '',
  fuente_id INTEGER REFERENCES fuente(id),
  radar_item_id INTEGER REFERENCES radar_item(id),
  fecha_oportunidad TEXT,
  estado TEXT NOT NULL DEFAULT 'NUEVA' CHECK (estado IN
    ('NUEVA','EVALUADA','SELECCIONADA','EN_PRODUCCION','PRODUCIDA','DESCARTADA','ARCHIVADA')),
  responsable TEXT NOT NULL DEFAULT 'Didi',
  proxima_accion TEXT NOT NULL DEFAULT '',
  puntuacion INTEGER NOT NULL DEFAULT 0 CHECK (puntuacion BETWEEN 0 AND 100),
  puntuacion_detalle TEXT NOT NULL DEFAULT '{}',
  creado_en TEXT NOT NULL,
  actualizado_en TEXT NOT NULL
) STRICT;

CREATE TABLE pieza (
  id INTEGER PRIMARY KEY,
  codigo TEXT NOT NULL UNIQUE,
  producto_id INTEGER NOT NULL REFERENCES producto(id),
  campana_id INTEGER REFERENCES campana(id),
  idea_id INTEGER REFERENCES idea(id),
  formato TEXT NOT NULL,
  canal TEXT NOT NULL,
  titulo TEXT NOT NULL,
  tipo_afirmacion TEXT NOT NULL CHECK (tipo_afirmacion IN
    ('EDUCATIVA','PROMOCIONAL','DESARROLLO','NOTICIA','HUMOR','CAPTACION')),
  estado TEXT NOT NULL DEFAULT 'BORRADOR' CHECK (estado IN
    ('BORRADOR','EN_REVISION','CORRECCIONES','LISTA_PARA_APROBAR','APROBADA','PROGRAMADA','PUBLICADA','ARCHIVADA','RECHAZADA')),
  version_actual INTEGER NOT NULL DEFAULT 0,
  fecha_prevista TEXT,
  plantilla TEXT,
  creado_en TEXT NOT NULL,
  actualizado_en TEXT NOT NULL
) STRICT;

CREATE TABLE pieza_version (
  id INTEGER PRIMARY KEY,
  pieza_id INTEGER NOT NULL REFERENCES pieza(id),
  numero INTEGER NOT NULL CHECK (numero >= 1),
  contenido TEXT NOT NULL,                     -- JSON: gancho, copy, cta, textos de plantilla, guion
  capacidades TEXT NOT NULL DEFAULT '[]',      -- códigos de capacidad que la pieza afirma
  fuentes TEXT NOT NULL DEFAULT '[]',          -- ids de radar_item o URLs primarias
  hash TEXT NOT NULL,
  autor TEXT NOT NULL,
  nota TEXT NOT NULL DEFAULT '',
  creado_en TEXT NOT NULL,
  UNIQUE (pieza_id, numero)
) STRICT;

CREATE TABLE licencia_recurso (
  id INTEGER PRIMARY KEY,
  recurso TEXT NOT NULL UNIQUE,
  tipo TEXT NOT NULL CHECK (tipo IN ('TIPOGRAFIA','ICONOS','IMAGEN','MUSICA','EFECTO','SOFTWARE','PLANTILLA','VOZ')),
  licencia TEXT NOT NULL,
  url TEXT NOT NULL,
  uso_comercial INTEGER NOT NULL CHECK (uso_comercial IN (0,1)),
  atribucion TEXT NOT NULL DEFAULT '',
  verificado_en TEXT NOT NULL,
  notas TEXT NOT NULL DEFAULT ''
) STRICT;

CREATE TABLE activo (
  id INTEGER PRIMARY KEY,
  pieza_id INTEGER REFERENCES pieza(id),
  version INTEGER,
  ruta TEXT NOT NULL,
  tipo TEXT NOT NULL,                          -- imagen, pdf, video, audio, html, srt, fuente
  formato TEXT NOT NULL DEFAULT '',            -- 1080x1350, vertical, etc.
  sha256 TEXT NOT NULL,
  bytes INTEGER NOT NULL,
  ancho INTEGER,
  alto INTEGER,
  duracion_ms INTEGER,
  origen TEXT NOT NULL CHECK (origen IN ('RENDER','CAPTURA','GRABACION','STOCK','IA_GENERATIVA','EXTERNO')),
  licencia_id INTEGER REFERENCES licencia_recurso(id),
  creado_en TEXT NOT NULL,
  UNIQUE (ruta, sha256)
) STRICT;

CREATE TABLE revision (
  id INTEGER PRIMARY KEY,
  pieza_id INTEGER NOT NULL REFERENCES pieza(id),
  version INTEGER NOT NULL,
  revisor TEXT NOT NULL,                       -- AUDITOR_AUTOMATICO, HUMANO, nombre del agente
  resultado TEXT NOT NULL CHECK (resultado IN ('APROBADO','CON_OBSERVACIONES','RECHAZADO')),
  hallazgos TEXT NOT NULL DEFAULT '[]',
  creado_en TEXT NOT NULL
) STRICT;

CREATE TABLE aprobacion (
  id INTEGER PRIMARY KEY,
  pieza_id INTEGER NOT NULL REFERENCES pieza(id),
  version INTEGER NOT NULL,
  hash_version TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('APROBADA','RECHAZADA','CORRECCIONES')),
  comentario TEXT NOT NULL DEFAULT '',
  decidido_por TEXT NOT NULL,
  decidido_en TEXT NOT NULL
) STRICT;

CREATE TABLE publicacion (
  id INTEGER PRIMARY KEY,
  pieza_id INTEGER NOT NULL REFERENCES pieza(id),
  version INTEGER NOT NULL,
  canal TEXT NOT NULL,
  cuenta TEXT NOT NULL DEFAULT '',
  copy TEXT NOT NULL,
  archivos TEXT NOT NULL DEFAULT '[]',
  fecha_prevista TEXT,
  estado TEXT NOT NULL DEFAULT 'PAQUETE_LISTO' CHECK (estado IN
    ('PAQUETE_LISTO','PROGRAMADA','PUBLICADA','FALLIDA','CANCELADA')),
  metodo TEXT NOT NULL DEFAULT 'MANUAL' CHECK (metodo IN ('MANUAL','PROGRAMADOR_NATIVO','API_OFICIAL')),
  id_externo TEXT,
  url TEXT,
  publicada_en TEXT,
  error TEXT,
  reintentos INTEGER NOT NULL DEFAULT 0,
  creado_en TEXT NOT NULL,
  actualizado_en TEXT NOT NULL,
  -- No se puede decir «publicada» sin una prueba externa de que lo está.
  CHECK (estado <> 'PUBLICADA' OR ((url IS NOT NULL OR id_externo IS NOT NULL) AND publicada_en IS NOT NULL)),
  CHECK (estado <> 'FALLIDA' OR error IS NOT NULL)
) STRICT;

CREATE TABLE metrica (
  id INTEGER PRIMARY KEY,
  publicacion_id INTEGER REFERENCES publicacion(id),
  campana_id INTEGER REFERENCES campana(id),
  fecha TEXT NOT NULL,
  nombre TEXT NOT NULL CHECK (nombre IN (
    'impresiones','alcance','visualizaciones','retencion_promedio_ms','reacciones','comentarios','compartidos',
    'guardados','clics','visitas','leads','formularios','conversaciones','solicitudes_demo','demos_realizadas',
    'ventas','ingresos_c','horas_produccion_min','gasto_c','correcciones','errores_factuales','fallos_publicacion')),
  valor INTEGER NOT NULL,
  naturaleza TEXT NOT NULL CHECK (naturaleza IN ('MEDIDA','ESTIMADA')),
  origen TEXT NOT NULL CHECK (origen IN ('MANUAL','CSV','API','SISTEMA')),
  nota TEXT NOT NULL DEFAULT '',
  creado_en TEXT NOT NULL,
  CHECK (publicacion_id IS NOT NULL OR campana_id IS NOT NULL),
  UNIQUE (publicacion_id, campana_id, fecha, nombre, naturaleza, origen)
) STRICT;

CREATE TABLE lead (
  id INTEGER PRIMARY KEY,
  uid TEXT NOT NULL UNIQUE,
  ingreso_en TEXT NOT NULL,
  producto_id INTEGER NOT NULL REFERENCES producto(id),
  fuente TEXT NOT NULL,
  campana_id INTEGER REFERENCES campana(id),
  problema_principal TEXT NOT NULL DEFAULT '',
  nombre TEXT NOT NULL DEFAULT '',
  email TEXT,
  telefono TEXT,
  empresas_que_lleva INTEGER CHECK (empresas_que_lleva IS NULL OR empresas_que_lleva >= 0),
  estado TEXT NOT NULL DEFAULT 'NUEVO' CHECK (estado IN
    ('NUEVO','CONTACTADO','CUALIFICADO','DEMO_AGENDADA','DEMO_HECHA','BETA','PROPUESTA','GANADO','PERDIDO','NO_CONTACTAR')),
  proxima_accion TEXT NOT NULL DEFAULT '',
  seguimiento_en TEXT,
  -- Ley 29733 y su reglamento (D.S. 016-2024-JUS): consentimiento para atender la solicitud y, por separado,
  -- para recibir publicidad. Se guarda la prueba: cuándo, con qué texto (versión) y por qué medio.
  consentimiento INTEGER NOT NULL DEFAULT 0 CHECK (consentimiento IN (0,1)),
  consentimiento_publicidad INTEGER NOT NULL DEFAULT 0 CHECK (consentimiento_publicidad IN (0,1)),
  finalidad TEXT NOT NULL DEFAULT '',
  consentimiento_en TEXT,
  consentimiento_version TEXT,
  consentimiento_medio TEXT,
  baja_en TEXT,
  clave_dedup TEXT NOT NULL UNIQUE,
  notas TEXT NOT NULL DEFAULT '',
  actualizado_en TEXT NOT NULL,
  CHECK (email IS NOT NULL OR telefono IS NOT NULL),
  CHECK (consentimiento = 0 OR (consentimiento_en IS NOT NULL AND finalidad <> '')),
  CHECK (consentimiento_publicidad = 0 OR consentimiento = 1),
  CHECK (baja_en IS NULL OR consentimiento_publicidad = 0)
) STRICT;

-- Quien pidió la baja o la supresión no vuelve a recibir publicidad aunque se reimporte una lista vieja.
-- Solo se guarda el hash del contacto normalizado, no el contacto.
CREATE TABLE lista_supresion (
  hash TEXT PRIMARY KEY,
  motivo TEXT NOT NULL CHECK (motivo IN ('BAJA','SUPRESION')),
  en TEXT NOT NULL
) STRICT;

CREATE TABLE lead_evento (
  id INTEGER PRIMARY KEY,
  lead_id INTEGER NOT NULL REFERENCES lead(id) ON DELETE CASCADE,
  en TEXT NOT NULL,
  tipo TEXT NOT NULL,
  detalle TEXT NOT NULL DEFAULT ''
) STRICT;

CREATE TABLE experimento (
  id INTEGER PRIMARY KEY,
  codigo TEXT NOT NULL UNIQUE,
  campana_id INTEGER REFERENCES campana(id),
  hipotesis TEXT NOT NULL,
  cambio TEXT NOT NULL,
  variable TEXT NOT NULL,
  metrica TEXT NOT NULL,
  inicio TEXT,
  fin TEXT,
  resultado TEXT NOT NULL DEFAULT '',
  limitaciones TEXT NOT NULL DEFAULT '',
  decision TEXT CHECK (decision IS NULL OR decision IN ('CONTINUAR','MODIFICAR','DETENER','INVESTIGAR')),
  estado TEXT NOT NULL DEFAULT 'PLANIFICADO' CHECK (estado IN ('PLANIFICADO','EN_CURSO','TERMINADO','CANCELADO'))
) STRICT;

CREATE TABLE tarea (
  id INTEGER PRIMARY KEY,
  codigo TEXT NOT NULL UNIQUE,
  agente TEXT NOT NULL,
  objetivo TEXT NOT NULL,
  entradas TEXT NOT NULL DEFAULT '{}',
  restricciones TEXT NOT NULL DEFAULT '[]',
  salida_esperada TEXT NOT NULL,
  estado TEXT NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN
    ('PENDIENTE','PREPARADA','EN_CURSO','REQUIERE_APROBACION','COMPLETADA','FALLIDA','CANCELADA')),
  modo TEXT NOT NULL CHECK (modo IN ('DETERMINISTA','ASISTIDO','LOCAL','EXTERNO')),
  resultado TEXT,
  evidencias TEXT NOT NULL DEFAULT '[]',
  errores TEXT NOT NULL DEFAULT '[]',
  coste_estimado_c INTEGER NOT NULL DEFAULT 0,
  coste_real_c INTEGER NOT NULL DEFAULT 0,
  requiere_aprobacion INTEGER NOT NULL DEFAULT 0 CHECK (requiere_aprobacion IN (0,1)),
  intentos INTEGER NOT NULL DEFAULT 0,
  max_intentos INTEGER NOT NULL DEFAULT 3 CHECK (max_intentos BETWEEN 1 AND 5),
  padre_id INTEGER REFERENCES tarea(id),
  profundidad INTEGER NOT NULL DEFAULT 0 CHECK (profundidad BETWEEN 0 AND 3),
  clave_idempotencia TEXT NOT NULL,
  vence_en TEXT,
  creado_en TEXT NOT NULL,
  actualizado_en TEXT NOT NULL,
  -- Ninguna tarea se marca completada sin resultado.
  CHECK (estado <> 'COMPLETADA' OR resultado IS NOT NULL)
) STRICT;

CREATE UNIQUE INDEX ux_tarea_activa ON tarea (clave_idempotencia)
  WHERE estado IN ('PENDIENTE','PREPARADA','EN_CURSO','REQUIERE_APROBACION');

CREATE TABLE tarea_evento (
  id INTEGER PRIMARY KEY,
  tarea_id INTEGER NOT NULL REFERENCES tarea(id),
  en TEXT NOT NULL,
  tipo TEXT NOT NULL,
  detalle TEXT NOT NULL DEFAULT ''
) STRICT;

CREATE TABLE registro_error (
  id INTEGER PRIMARY KEY,
  en TEXT NOT NULL,
  modulo TEXT NOT NULL,
  codigo TEXT NOT NULL,
  mensaje TEXT NOT NULL,
  detalle TEXT NOT NULL DEFAULT '',
  resuelto INTEGER NOT NULL DEFAULT 0 CHECK (resuelto IN (0,1))
) STRICT;

CREATE TABLE herramienta (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  nombre TEXT NOT NULL,
  categoria TEXT NOT NULL,
  url TEXT NOT NULL,
  funcion TEXT NOT NULL,
  coste TEXT NOT NULL,
  licencia TEXT NOT NULL,
  limites TEXT NOT NULL DEFAULT '',
  requisitos TEXT NOT NULL DEFAULT '',
  automatizacion TEXT NOT NULL DEFAULT '',
  privacidad TEXT NOT NULL DEFAULT '',
  riesgo TEXT NOT NULL DEFAULT '',
  decision TEXT NOT NULL CHECK (decision IN ('ADOPTAR','PROBAR','DESCARTAR','RESERVAR')),
  verificacion TEXT NOT NULL,
  verificado_en TEXT NOT NULL,
  requiere_autorizacion INTEGER NOT NULL DEFAULT 0 CHECK (requiere_autorizacion IN (0,1))
) STRICT;

-- Permisos revocables para automatizar categorías concretas (nivel 3 de publicación, por ejemplo).
CREATE TABLE autorizacion (
  id INTEGER PRIMARY KEY,
  categoria TEXT NOT NULL,
  alcance TEXT NOT NULL,
  otorgada_por TEXT NOT NULL,
  otorgada_en TEXT NOT NULL,
  revocada_en TEXT,
  nota TEXT NOT NULL DEFAULT ''
) STRICT;

CREATE TABLE gasto (
  id INTEGER PRIMARY KEY,
  producto_id INTEGER REFERENCES producto(id),
  concepto TEXT NOT NULL,
  importe_c INTEGER NOT NULL CHECK (importe_c >= 0),
  moneda TEXT NOT NULL DEFAULT 'PEN',
  recurrente INTEGER NOT NULL DEFAULT 0 CHECK (recurrente IN (0,1)),
  aprobado_por TEXT NOT NULL,
  aprobado_en TEXT NOT NULL,
  fecha TEXT NOT NULL
) STRICT;

CREATE TABLE ajuste (
  clave TEXT PRIMARY KEY,
  valor TEXT NOT NULL
) STRICT;

CREATE TABLE auditoria (
  id INTEGER PRIMARY KEY,
  en TEXT NOT NULL,
  actor TEXT NOT NULL,
  entidad TEXT NOT NULL,
  entidad_id INTEGER,
  accion TEXT NOT NULL,
  detalle TEXT NOT NULL DEFAULT '{}'
) STRICT;

CREATE INDEX ix_idea_producto_estado ON idea (producto_id, estado, puntuacion DESC);
CREATE INDEX ix_pieza_fecha ON pieza (fecha_prevista, estado);
CREATE INDEX ix_publicacion_fecha ON publicacion (fecha_prevista, estado);
CREATE INDEX ix_lead_seguimiento ON lead (estado, seguimiento_en);
CREATE INDEX ix_tarea_estado ON tarea (estado, agente);
CREATE INDEX ix_radar_estado ON radar_item (estado_verificacion, detectado_en DESC);
