# Receptor del formulario (Cloudflare Workers + D1)

Recibe las inscripciones de la landing, las guarda solo con consentimiento y deja que tu PC las traiga y las borre del servidor. **No está desplegado.** Desplegarlo crea una cuenta y un servicio en Internet: necesita tu autorización explícita.

## Por qué así

- Decisión del registro de herramientas (`docs/REGISTRO-HERRAMIENTAS-Y-COSTES.md`, sección 14): Cloudflare Pages para la página y Workers + D1 para el formulario, en el plan gratuito.
- Límites del plan gratuito al 14/10/2026: 100 000 solicitudes al día en Workers; D1 con 5 millones de filas leídas, 100 000 escritas al día y 5 GB. Si se superan, el servicio se corta hasta las 00:00 UTC; no se cobra.
- **Pendiente de confirmar:** si Cloudflare pide tarjeta para crear la cuenta o usar D1. Si la pide, para ahí y avísame: no se introduce ninguna tarjeta sin tu autorización.
- Código propio y sin dependencias: lo puedes leer entero en `worker.js`.

## Qué guarda y qué no

| Guarda | No guarda |
| --- | --- |
| Nombre, correo, cuántas empresas lleva y qué le quita tiempo (opcional) | La IP: solo su huella SHA-256 con una sal secreta, para limitar a 5 envíos por hora y como parte de la prueba del consentimiento |
| Consentimiento (obligatorio), publicidad aparte (opcional), si pidió demostración | Cookies, ni nada del navegador |
| Versión del aviso que aceptó, fecha y hora, origen de la visita (utm) | Nada sin la casilla de consentimiento marcada |

Un robot que llena el campo oculto recibe «ok» y no se guarda nada.

## Antes de desplegar

`python -m mos sitio pendientes` tiene que decir que no falta nada legal: datos del responsable, banco de datos inscrito, flujo transfronterizo comunicado y aviso revisado por un abogado.

## Pasos (cuando lo autorices)

Necesitas Node.js 20 o superior. `npx` descarga Wrangler, la herramienta oficial de Cloudflare (licencia MIT o Apache-2.0).

```powershell
cd sitio\receptor
npx wrangler login                                   # abre el navegador para entrar a tu cuenta de Cloudflare
npx wrangler d1 create cuadra-lista                  # copia el database_id que muestra
copy wrangler.toml.ejemplo wrangler.toml             # y pega el database_id y la dirección de la landing
npx wrangler d1 execute cuadra-lista --remote --file=schema.sql
npx wrangler secret put SAL                          # pega un texto aleatorio de 32 caracteres o más
npx wrangler secret put CLAVE_EXPORTAR               # otro texto aleatorio; guárdalo en tu gestor de contraseñas
npx wrangler deploy                                  # te da la dirección https del receptor
```

Para generar un texto aleatorio: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

Luego, en `sitio/sitio.toml`: `publicacion.receptor = "https://…/api/lista"` y `publicacion.url` con la dirección de la landing. Construye y sube la página:

```powershell
python -m mos sitio construir --publicable
npx wrangler pages deploy sitio\dist --project-name cuadra-beta
```

## Traer las inscripciones a tu PC

La clave nunca va en archivos: se pone en la consola solo para ese comando.

```powershell
$env:MOS_CLAVE_LISTA = "la clave de CLAVE_EXPORTAR"
python -m mos sitio importar          # las guarda en tu base con su consentimiento y las borra del servidor
Remove-Item Env:MOS_CLAVE_LISTA
```

Si alguna fila no entra, no se borra nada del servidor y el comando lo dice. Con `--sin-borrar` las deja allá.

## Pruebas

```powershell
node --test sitio/receptor/worker.test.mjs
```

Prueban, con una D1 simulada en SQLite: que sin consentimiento no se guarda nada, que no hay duplicados ni IP en claro, la trampa para robots, el límite por hora, que exportar y borrar exigen la clave y que las reglas coinciden con las de `mos/sitio.py`.
