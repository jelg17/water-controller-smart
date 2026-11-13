# Water Controller Smart

Aplicación web para el monitoreo y control del consumo de agua. Permite a cada
usuario registrar sus actividades de consumo, calcular los litros utilizados,
definir una meta diaria y recibir alertas, tanto en la aplicación como por correo
electrónico, cuando el consumo supera los valores recomendados.

## Contenido

1. [Funcionalidades](#funcionalidades)
2. [Tecnologías](#tecnologías)
3. [Requisitos](#requisitos)
4. [Instalación y ejecución](#instalación-y-ejecución)
5. [Configuración](#configuración)
6. [Estructura del proyecto](#estructura-del-proyecto)
7. [Base de datos](#base-de-datos)
8. [API](#api)
9. [Seguridad](#seguridad)
10. [Limitaciones conocidas](#limitaciones-conocidas)
11. [Versión anterior](#versión-anterior)

## Funcionalidades

- **Registro de actividades.** Mediante cronómetro o ingresando la duración en
  minutos (US-001).
- **Cálculo del consumo.** Litros consumidos a partir de la duración y el caudal de
  cada actividad (US-002).
- **Detección de excesos.** Marca las actividades que superan el tiempo recomendado
  y clasifica el consumo diario como Normal, Precaución o Exceso (US-003).
- **Alertas.** Notificaciones en la interfaz web y por correo electrónico (US-004).
- **Historial y reportes.** Consulta por periodo, gráficas de consumo, comparación
  con el periodo anterior, ahorro potencial y exportación a CSV (US-005 y US-006).
- **Personalización.** Caudal y tiempo recomendado ajustables por actividad
  (US-007).
- **Meta diaria.** Límite de consumo y porcentaje de aviso configurables
  (US-008).
- **Actividades propias.** Además de las actividades predeterminadas (ducha, lavado
  de platos, riego y aseo), cada usuario puede crear las suyas indicando nombre,
  caudal y tiempo recomendado. Se pueden editar y eliminar; los registros históricos
  se conservan.

## Tecnologías

- Python con Flask
- SQLite (módulo estándar `sqlite3`)
- HTML, CSS y JavaScript sin frameworks de frontend
- SMTP para el envío de correos

## Requisitos

- Python 3.9 o superior
- Las dependencias de `requirements.txt` (Flask y python-dotenv)
- Una cuenta en un servicio SMTP, solo si se desea el envío de alertas por correo

## Instalación y ejecución

1. Clonar el repositorio:

       git clone https://github.com/jelg17/water-controller-smart.git
       cd water-controller-smart

2. Instalar las dependencias:

       pip install -r requirements.txt

3. Configurar las variables de entorno (ver [Configuración](#configuración)).

4. Iniciar la aplicación:

       python app.py

La aplicación queda disponible en http://localhost:7500. Para detenerla, presionar
`Ctrl + C`. La base de datos `water.db` se crea automáticamente en el primer
arranque.

## Configuración

La configuración se realiza con variables de entorno, que pueden definirse en un
archivo `.env` ubicado junto a `app.py`. El repositorio incluye `.env.example` como
plantilla.

| Variable | Descripción | Obligatoria |
|---|---|---|
| `WCS_SMTP_SERVIDOR` | Servidor SMTP, por ejemplo `smtp-relay.brevo.com` | Solo para correo |
| `WCS_SMTP_PUERTO` | `587` (STARTTLS, valor por defecto) o `465` (SSL) | No |
| `WCS_SMTP_USUARIO` | Usuario o login SMTP | Solo para correo |
| `WCS_SMTP_CLAVE` | Contraseña o clave SMTP | Solo para correo |
| `WCS_SMTP_REMITENTE` | Dirección de remitente, verificada en el servicio SMTP. Si no se define, se usa el usuario | No |
| `WCS_SECRET_KEY` | Llave con la que se firman las sesiones. Si no se define, se genera una al iniciar y las sesiones se cierran con cada reinicio | Recomendada |

Si el servicio de correo no está configurado, la aplicación funciona con normalidad:
las alertas se registran y se muestran en la web, y el envío del correo queda
marcado como fallido.

El archivo `.env` contiene credenciales. Está incluido en `.gitignore` y no debe
subirse al repositorio.

### Alertas por correo

Se envía correo cuando el consumo del día alcanza el porcentaje de aviso de la meta
diaria (alerta preventiva) o la supera (alerta correctiva). Las alertas por exceso
de tiempo en una actividad se muestran únicamente en la interfaz web. Todas las
alertas quedan almacenadas y pueden consultarse en la sección Alertas.

## Estructura del proyecto

    app.py                     Servidor Flask: rutas, cálculos, validaciones y alertas
    db.py                      Acceso a la base de datos SQLite
    correo.py                  Envío de correos por SMTP
    requirements.txt           Dependencias de Python
    .env.example               Plantilla de configuración
    templates/                 Páginas HTML (login, registro, panel, historial,
                               configuración y alertas)
    static/css/estilos.css     Estilos
    static/js/panel.js         Cronómetro, registro y resumen del día
    static/js/historial.js     Historial, estadísticas y exportación CSV
    static/js/configuracion.js Meta diaria, caudales, tiempos y actividades propias
    static/js/alertas.js       Listado de alertas
    static/js/graficas.js      Gráficas SVG
    static/js/menu.js          Menú lateral

## Base de datos

SQLite, almacenada en `water.db`. Todas las tablas de datos incluyen `usuario_id`,
por lo que cada usuario accede únicamente a su propia información.

    usuarios ──< configuracion               Meta diaria y porcentaje de aviso
             ──< personalizaciones           Caudal y tiempo de actividades predeterminadas
             ──< actividades_personalizadas  Actividades creadas por el usuario
             ──< cronometros                 Cronómetro en marcha (máximo uno)
             ──< actividades                 Registros de consumo
             ──< alertas                     Alertas generadas

## API

Todas las rutas requieren una sesión iniciada. Sin sesión responden `401`.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/estado` | Catálogo de actividades, cronómetro y resumen del día |
| GET | `/api/historial` | Historial y estadísticas por periodo |
| GET | `/api/alertas` | Alertas del usuario |
| POST | `/api/cronometro/iniciar` | Inicia el cronómetro de una actividad |
| POST | `/api/cronometro/detener` | Detiene el cronómetro y registra la actividad |
| POST | `/api/actividad` | Registra una actividad con su duración en minutos |
| POST | `/api/caudal` | Guarda el caudal de una actividad |
| POST | `/api/tiempo-recomendado` | Guarda el tiempo recomendado de una actividad |
| POST | `/api/meta-diaria` | Guarda la meta diaria |
| POST | `/api/porcentaje-aviso` | Guarda el porcentaje de aviso |
| POST | `/api/actividad-personalizada` | Crea una actividad propia |
| POST | `/api/actividad-personalizada/eliminar` | Elimina una actividad propia |

## Seguridad

- Las contraseñas se almacenan únicamente como hash.
- Cada consulta y modificación se limita al usuario con sesión iniciada.
- Las credenciales del servicio de correo se leen de variables de entorno y no
  forman parte del código ni del repositorio.
- Las actividades propias se eliminan de forma lógica, de modo que el historial
  conserva el nombre con el que fueron registradas.

## Limitaciones conocidas

- La aplicación se ejecuta con el servidor de desarrollo de Flask y escucha solo en
  `127.0.0.1`. Para un despliegue en producción se requiere un servidor WSGI y un
  proxy inverso con HTTPS.
- SQLite es adecuada para un entorno de un solo servidor y baja concurrencia.
- El envío de correo no distingue la causa del fallo: ante cualquier error informa
  que el servicio no respondió.

## Versión anterior

El proyecto inició como una maqueta que almacenaba facturas en el `localStorage`
del navegador. Los siguientes archivos pertenecen a esa versión, permanecen en el
repositorio y ya no se utilizan: `servidor.py`, `index.html`, `factura.html`,
`datos.json`, `almacen.js`, `calculos.js`, `factura.js` y `login.js`.