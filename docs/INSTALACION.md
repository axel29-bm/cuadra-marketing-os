# Instalación en Windows

Tiempo estimado: 15 minutos para el núcleo. Todo es gratuito.

## 1. Lo mínimo (núcleo, agentes en modo asistido, auditor, leads, métricas)

1. **Python 3.12.** En PowerShell:
   ```powershell
   winget install Python.Python.3.12
   ```
   O descárgalo de python.org y marca «Add python.exe to PATH». Comprueba con `python --version`.
2. **Git** (si no lo tienes): `winget install Git.Git`.
3. **El repositorio**, en una carpeta que **no** esté dentro de OneDrive, Google Drive ni Dropbox:
   ```powershell
   mkdir C:\MarketingOS
   cd C:\MarketingOS
   git clone https://github.com/axel29-bm/cuadra-marketing-os.git
   cd cuadra-marketing-os
   ```
4. **Iniciar:**
   ```powershell
   python -m mos iniciar
   python -m mos estado
   ```
   Se crea `espacio\mos.db` con la configuración de Cuadra cargada.
5. **Abrir el panel:**
   ```powershell
   python -m mos web
   ```
   Se abre `http://127.0.0.1:8765` en tu navegador. Solo responde desde tu PC: si otra máquina o una página web intenta entrar, se rechaza. Para cerrarlo, Ctrl+C en la consola. Si el puerto está ocupado: `$env:MOS_PUERTO = "8766"`.
6. **Comprobar que todo funciona:**
   ```powershell
   python -m unittest discover -s tests -t .
   ```
   Debe terminar en `OK`.

> Si tu carpeta de usuario está sincronizada con OneDrive, define la carpeta de datos fuera de ella:
> `setx MOS_ESPACIO C:\MarketingOS\espacio` y abre una consola nueva.

## 2. Fábrica de contenidos y landing (imágenes, PDF, vídeo y la página de la lista de espera)

1. Dependencias de Python:
   ```powershell
   python -m pip install -r requirements.txt
   ```
2. Navegador para renderizar: en Windows el sistema usa **Microsoft Edge**, que ya está instalado. No hace falta descargar otro. Si prefieres Chromium: `python -m playwright install chromium`.
3. **FFmpeg** para vídeo y audio:
   ```powershell
   winget install Gyan.FFmpeg
   ```
   Comprueba con `ffmpeg -version`. Se usa como programa externo; no se distribuye con el sistema.
4. **Comprobar:**
   ```powershell
   python -m mos fabrica plantillas              # lista las plantillas y sus formatos
   python -m mos sitio ver                       # abre la landing en http://127.0.0.1:8766 (solo en tu PC)
   ```
5. **Node.js 22** (opcional): solo para correr las pruebas del receptor del formulario (`node --test sitio/receptor/worker.test.mjs`). `winget install OpenJS.NodeJS.LTS`.

## 3. IA local (opcional)

Solo si tu PC tiene al menos 16 GB de RAM. Con 8 GB funciona el modelo más pequeño, pero lento.

1. `winget install Ollama.Ollama`
2. Descarga un modelo (Apache-2.0, uso comercial permitido):
   ```powershell
   ollama pull qwen3.5:4b      # unos 3.3 a 4 GB; para PC de 16 GB
   ```
3. Activa el modo local para la sesión:
   ```powershell
   $env:MOS_IA_MODO = "LOCAL"
   $env:MOS_IA_MODELO = "qwen3.5:4b"
   python -m mos tarea ejecutar T-0001
   ```

## 4. Lo que no se instala sin autorización de Didi

- Ningún servicio en la nube que pida tarjeta.
- Ninguna clave de IA de pago.
- Ningún programador de publicaciones conectado por API a las redes.
- El despliegue público de la landing.

## 5. Actualizar

```powershell
git pull
python -m mos iniciar      # aplica migraciones nuevas y recarga la configuración, sin perder datos
python -m mos respaldar    # antes de cualquier cambio grande
```

## 6. Restaurar una copia de seguridad

`python -m mos respaldar` guarda en `espacio\respaldos` una copia verificada y conserva las 14 más recientes. Para volver a una:

1. Cierra el panel (Ctrl+C) y cualquier consola que use la base.
2. Aparta la base actual, sin borrarla:
   ```powershell
   Rename-Item espacio\mos.db mos-danada.db
   Remove-Item espacio\mos.db-wal, espacio\mos.db-shm -ErrorAction SilentlyContinue
   ```
3. Copia la copia elegida con el nombre de la base:
   ```powershell
   Copy-Item espacio\respaldos\mos-AAAAMMDDTHHMMSS…Z.db espacio\mos.db
   python -m mos estado
   ```
4. Si `estado` responde bien, puedes borrar `mos-danada.db` cuando quieras.

Las imágenes y vídeos exportados (`espacio\salidas`) no van dentro de la base: se regeneran con `python -m mos campana render …`.

## Problemas frecuentes

| Mensaje | Qué hacer |
| --- | --- |
| `python no se reconoce` | Reinstala Python marcando «Add to PATH», o usa `py` en lugar de `python` |
| `La base es de una versión más nueva` | Actualiza el repositorio con `git pull` |
| `database is locked` | Cierra otras consolas que estén usando la misma base |
| Caracteres raros en la consola | Ejecuta `chcp 65001` antes de los comandos |
