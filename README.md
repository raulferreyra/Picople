# Picople

> Gestor de fotos y videos **local y privado** para Windows, con base de datos **cifrada** y visor embebido (imágenes & video).

> Este Readme ha sido auto generado por IA, estoy cansado, luego modificaré y haré las correcciones.

---

## 🎯 Objetivo

Organizar tu biblioteca **en tu equipo** (sin nube), con miniaturas rápidas, álbumes automáticos por carpetas, **favoritos**, visor fluido y una base SQLCipher cifrada. Roadmap inmediato: **Personas y Mascotas** on‑device.

---

## ✨ Características (hitos completados)

1) **Bootstrap del proyecto**  
   - Estructura modular (`app/`, `controllers/`, `infrastructure/`, `core/`, `views/`, `assets/`).  
   - `venv`, dependencias, fuentes (Orgon) y favicon.

2) **UI base + theming**  
   - Ventana principal, sidebar, toolbar unificada.  
   - Modo **claro/oscuro** persistente (`QSettings`) y QSS aplicado.

3) **Carpetas**  
   - Vista “Carpetas” en grilla con scroll, agregar/quitar/abrir, selección múltiple.

4) **Pulido UX**  
   - Barra de estado, controles de búsqueda/recarga estilizados.

5) **Almacenamiento e indexación**  
   - **DB cifrada** (SQLCipher vía `pysqlcipher3`/`sqlcipher3`).  
   - Indexador en **QThread**. Miniaturas: imágenes (Pillow) y videos (FFmpeg vía `imageio-ffmpeg`).  
   - Esquema: `media(path, kind, mtime, size, thumb_path, favorite)`, `folders`, `albums`, `album_media`.

6) **Colección**  
   - Grilla con **scroll infinito**, filtros (Todo/Fotos/Videos) y búsqueda por texto.  
   - Delegate propio: respeta aspecto, elipsis; icono de “play” en videos.

7) **Preferencias**  
   - Detección rápida de HW y “configuración sugerida”.  
   - **Ajustes runtime** (tile size, batch, thumbs de video, etc.).

8) **Visor embebido** (imágenes & video)  
   - **ImageView**: fit/100%/zoom/rotate, wheel & drag.  
   - **VideoView**: play/pause, barra de progreso, volumen, mute.  
   - Atajos: ← → Espacio, Ctrl+0/1/±, R.  
   - Muestra/oculta controles según tipo (imagen vs video).

9) **Favoritos y Álbumes**  
   - `favorite` en `media`; tablas `albums` y `album_media`.  
   - Vista **Favoritos** (scroll, ♥).  
   - Vista **Álbumes** con portada, **renombrar**, y **detalle de álbum** embebido.  
   - **Dedupe por carpeta**: `folder_key` estable por álbum, **fusión** de duplicados al actualizar.  
   - Sincronización del estado con el visor (♥) y refresco de contadores.

---

## 🚧 Próximos hitos (resumen)

10. **Personas y Mascotas (on‑device)** – detección, embeddings, clustering, UI de confirmación/sugerencias.  
11. **Cosas y Lugares** – etiquetas por objeto/escena + EXIF GPS/time clustering.  
12. **Búsqueda avanzada** – facetas combinables (persona:cosa:lugar:fecha:álbum).  
13–20. Calidad/dedup, exportación, watcher en segundo plano, rendimiento, seguridad, empaquetado, “Moments” de video…

> Detalle completo de roadmap en el repositorio (sección “Hitos”).

---

## 🖥️ Requisitos

- **Windows 10/11**, Python **3.10+** (recomendado 3.11).  
- FFmpeg accesible (lo usa `imageio-ffmpeg` para generar thumbs y reproducir).  
- Para HEIC/HEIF: `pillow-heif` (opcional).  
- SQLCipher bindings: **`pysqlcipher3`** (Windows) o **`sqlcipher3`**.

---

## ⚙️ Instalación (desde fuente)

```powershell
# 1) Clonar
git clone https://github.com/raulferreyra/picople.git
cd picople

# 2) Entorno virtual
python -m venv .venv
.venv\Scripts\activate

# 3) Dependencias
pip install -U pip wheel
pip install PySide6 pillow imageio imageio-ffmpeg pillow-heif
pip install pysqlcipher3  # si falla, prueba: pip install sqlcipher3

# 4) Primer arranque
python -m picople.app.main
```

**Primer inicio**  

- Crea/ingresa **clave** de la base cifrada.  
- Agrega carpetas en la vista **Carpetas**.  
- Pulsa **Actualizar** para indexar (miniaturas).

---

## ▶️ Uso rápido

- **Colección**: grilla con filtros (Todo/Fotos/Videos) y **búsqueda**.  
- **Favoritos**: marca ♥ desde la grilla o el visor; se refleja en tiempo real.  
- **Álbumes**: generados por **carpeta** (clave `folder_key`); puedes **renombrar** títulos y elegir **portada** (menú contextual).  
- **Visor**: doble clic en una miniatura. Cerrar con ✕ (toolbar).

**Atajos**  

- Navegación: `←` `→`  
- Reproducción: `Espacio`  
- Zoom: `Ctrl +` / `Ctrl -` / `Ctrl 1` (100%) / `Ctrl 0` (Ajustar)  
- Rotar: `R`

---

## 🗃️ Esquema y reglas clave

- `media(path UNIQUE, kind, mtime, size, thumb_path, favorite INTEGER)`  
- `albums(id, title UNIQUE, cover_path, folder_key)`  
- `album_media(album_id, media_id, position, PRIMARY KEY(album_id, media_id))`

**Dedupe de álbumes**  

- `folder_key` = ruta **relativa a la raíz más larga que haga match**, normalizada (`/`, minúsculas).  
- Al pulsar **Actualizar** (indexación), Picople ejecuta:  
  1. Reconstrucción por carpetas (sin pisar títulos personalizados).  
  2. `repair_albums(roots)`: infiere `folder_key` por **frecuencia** de las medias, **fusiona duplicados** y conserva:  
     - el álbum con **título personalizado**,  
     - si no hay personalizado, el de **id menor**.  
  3. Migra portada y vínculos, borra duplicados, elimina álbumes vacíos.

---

## 🔐 Privacidad

- Todo el procesamiento es **local**.  
- La base usa **SQLCipher** (clave definida por el usuario).  
- Próximos módulos de ML (caras, objetos) serán **on‑device**.

---

## 🧰 Estructura

```
src/picople/
  app/
    main.py, main_window.py, views/
  controllers/
    MediaItem.py, MediaListModel.py, ...
  core/
    config.py, theme.py, paths.py, ...
  infrastructure/
    db.py, indexer.py, ...
  assets/
    qss, íconos, fuentes
```

---

## 🐞 Problemas conocidos

- Si `pysqlcipher3` no instala correctamente, prueba `sqlcipher3`.  
- En algunos mp4 rotados, la rotación depende de metadatos del contenedor; el visor respeta `displaymatrix` cuando FFmpeg lo reporta.  
- En bibliotecas **muy grandes**, incrementa `batch` y tamaño de tile en Preferencias para mejorar fluidez.

---

## 🤝 Contribuir

- Issues y PRs bienvenidos.  
- Sigue el estilo de imports (todos **arriba del archivo**), tipado y QSS existente.  
- Evita imports dentro de funciones/clases.

---

## 📄 Licencia

Por definir (temporalmente **All rights reserved** hasta estabilizar).

---

## 📝 Changelog (resumen)

- **0.1.0** – Hitos 1–9 completados (colección, visor, favoritos, álbumes con dedupe por `folder_key`, theming, indexación cifrada).
- **Next** – Hito 10: Personas y Mascotas (detección/embeddings/clustering + UI de sugerencias).
