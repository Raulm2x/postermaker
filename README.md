# PosterMaker 🎨🖼️

**PosterMaker** es una herramienta local de código abierto para Linux que convierte cualquier imagen en un póster gigante imprimible dividido en hojas individuales (**Carta, A4, A3, A5, Oficio o Tabloide**).

Genera un archivo PDF con una página por pieza listo para imprimir al 100 %, recortar y ensamblar en casa o en tu oficina. No requiere conexión a internet, no tiene límites de uso, no sube tus fotos a ningún servidor externo y no añade marcas de agua.

---

## Características principales

* **Cálculo automático de cuadrícula:** Define cuántas hojas de ancho o de alto deseas; la proporción se conserva sin deformar ni recortar la imagen original.
* **Formatos de papel en español e internacionales:** Carta (Letter), A4, A3, A5, Oficio (Legal) y Tabloide (Doble Carta).
* **Plano y guía de montaje visual:** Genera opcionalmente como primera página un esquema numerado con dimensiones en cm, líneas de corte e instrucciones paso a paso.
* **Gestor de inactividad inteligente:** El servidor web monitorea las conexiones y se apaga de forma autónoma tras un periodo de inactividad (o con un clic en la interfaz), liberando la memoria RAM y los archivos temporales.
* **Modos de color:**
  * **Color:** Conserva los tonos originales.
  * **Blanco y negro:** Escala de grises pura, ideal para impresoras monocromáticas.
  * **Alto contraste:** Umbral monocromático para ahorrar tinta o tóner.
* **Descarga en ZIP:** Permite descargar un archivo comprimido con cada hoja en alta resolución JPEG y un archivo de instrucciones de montaje.
* **Hoja de calibración:** Permite medir el margen físico que tu impresora no puede imprimir para que las uniones encajen con exactitud milimétrica.
* **Múltiples interfaces:** Interfaz web moderna y reactiva (HTML5/CSS3/Vanilla JS sin dependencias) y CLI potente para scripts y terminal.

---

## Instalación en cualquier distribución de Linux

PosterMaker está diseñado para instalarse y ejecutarse sin fricción en **Ubuntu, Debian, Fedora, Arch Linux, CachyOS, openSUSE, Manjaro, Linux Mint** o cualquier otra distribución.

### Opción 1: Binario autónomo (Recomendado - Sin necesidad de Python)

Puedes compilar o descargar un único archivo ejecutable portátil que contiene el entorno de ejecución, librerías gráficas, servidor y recursos web integrados:

```bash
# 1. Compilar el paquete autónomo
./scripts/build_standalone.sh

# 2. Instalar en tu usuario (~/.local/bin y menú de aplicaciones)
./dist/postermaker --install
```

O usando el script universal de instalación:

```bash
# Instalación para el usuario actual:
./scripts/install.sh

# O instalación global para todos los usuarios:
sudo ./scripts/install.sh
```

Una vez instalado:
* **Desde el menú de aplicaciones:** Busca y haz clic en **PosterMaker** (en GNOME, KDE Plasma, Hyprland, XFCE, Rofi, etc.).
* **Desde la terminal:** Ejecuta directamente `postermaker`.

### Opción 2: Instalación desde código fuente (Desarrollo con Python)

Requiere Python 3.10 o superior:

```bash
# Con uv (recomendado):
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"

# O con python3 venv y pip:
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### Opción 3: Aislado con `uv tool` o `pipx`

```bash
uv tool install .
# o con pipx:
pipx install .
```

### Opción 4: Contenedor Docker / Podman

```bash
docker compose up -d
```
Accede a <http://localhost:8000>.

---

## Uso de la interfaz Web

Inicia la aplicación ejecutando en tu terminal:

```bash
postermaker
```

O seleccionando **PosterMaker** en tu lanzador de aplicaciones. Se abrirá automáticamente tu navegador predeterminado en `http://127.0.0.1:8000`.

### Opciones del servidor:

```bash
postermaker --web --host 127.0.0.1 --port 8000 --idle-timeout 900
```

* `--host`: Dirección IP de escucha (por defecto `127.0.0.1`).
* `--port`: Puerto de escucha (por defecto `8000`; si no está disponible, prueba automáticamente con los siguientes de forma sucesiva hasta encontrar uno libre).
* `--idle-timeout`: Segundos de inactividad antes de liberar memoria y apagarse (por defecto `900`s / 15m; usa `0` para mantenerlo siempre activo).

---

## Uso de la línea de comandos (CLI)

PosterMaker incluye una potente interfaz de terminal para generar pósteres por lotes o automatizar impresiones:

```bash
postermaker foto.jpg \
  --pages-wide 4 \
  --paper carta \
  --orientation portrait \
  --color color \
  --margin 10 \
  --overlap 4 \
  --marks \
  --labels \
  --guide \
  --zip piezas.zip \
  -o mural.pdf
```

### Parámetros del CLI:

| Opción | Descripción |
| --- | --- |
| `image` | Ruta de la imagen de entrada (JPG, PNG o WebP). |
| `-o, --output` | Nombre del PDF generado (por defecto: `poster.pdf`). |
| `--pages-wide N` | Número de hojas de ancho (1 a 10). |
| `--pages-high N` | Número de hojas de alto (1 a 10; alternativa a `--pages-wide`). |
| `--paper PAPEL` | Tamaño de papel: `carta`, `letter`, `a4`, `a3`, `a5`, `oficio`, `legal`, `tabloide`, `tabloid`. |
| `--orientation TIPO` | `portrait` (vertical) o `landscape` (horizontal). |
| `--color MODO` | Modo de color: `color`, `grayscale` (escala de grises) o `monochrome` (alto contraste). |
| `--margin MM` | Margen no imprimible en milímetros por lado (por defecto: 10 mm). |
| `--margin-top/right/bottom/left` | Márgenes específicos por lado. |
| `--overlap MM` | Solapamiento entre hojas para recorte y pegado manual (por defecto: 0 mm). |
| `--dpi N` | Resolución de renderizado en ppp (72 a 600, por defecto: 300). |
| `--marks` | Añade marcas de corte en los bordes de cada hoja. |
| `--labels` | Añade numeración de fila y columna en el pie de página de cada hoja. |
| `--guide` | Incluye plano de montaje e instrucciones como primera página del PDF. |
| `--tiles DIR` | Guarda cada hoja individual como imagen JPEG en la carpeta indicada. |
| `--zip ARCHIVO.zip` | Comprime todas las hojas y las instrucciones en un archivo ZIP. |
| `--preview PNG` | Genera una vista previa del póster con la cuadrícula de corte dibujada. |
| `--calibration PAPEL` | Genera una hoja de calibración para el papel seleccionado y sale. |
| `--install` | Instala en el sistema (ejecutable, icono XDG y acceso `.desktop`). |
| `--uninstall` | Desinstala completamente la aplicación del sistema. |

### Ejemplos prácticos:

```bash
# Generar hoja de calibración en tamaño Carta:
postermaker --calibration carta -o calibracion-carta.pdf

# Crear un póster de 3 hojas de alto en blanco y negro con guía de montaje:
postermaker paisaje.png --pages-high 3 --paper a4 --color grayscale --guide -o poster.pdf

# Generar póster panorámico en Tabloide con solapamiento de 5 mm y archivo ZIP:
postermaker foto.jpg --pages-wide 5 --paper tabloide --overlap 5 --zip fotos_mural.zip -o poster.pdf
```

---

## Liberación de recursos y servicio systemd (Opcional)

Si utilizas un entorno con systemd (Arch, CachyOS, Ubuntu, Fedora, etc.) y deseas que PosterMaker consuma **0 MB de RAM en reposo**, puedes activar el socket de usuario:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/postermaker.socket systemd/postermaker.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now postermaker.socket
```

* **¿Cómo opera?** systemd vigila el puerto 8000 sin consumir memoria RAM. En cuanto abres `http://127.0.0.1:8000` en tu navegador o lanzador, systemd levanta el servidor al instante. Tras el tiempo de inactividad programado, el servidor se apaga y vuelve al reposo de 0 MB.

---

## Desinstalación

Para eliminar completamente PosterMaker del sistema:

```bash
postermaker --uninstall
# O con el script:
./scripts/uninstall.sh
```

---

## Ejecución de pruebas

El proyecto cuenta con una suite completa de pruebas unitarias y de integración:

```bash
.venv/bin/pytest
```

---

## Licencia

Distribuido bajo licencia MIT. Consulta el archivo `LICENSE` para más detalles.
