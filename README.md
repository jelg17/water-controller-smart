# Water Controller Smart

Aplicación web para controlar el consumo de agua del hogar. Cada persona crea su
cuenta, registra sus actividades (ducha, lavado de platos, riego, aseo o las que
ella misma cree), y la app calcula los litros gastados, avisa cuando se pasa del
tiempo recomendado o de su meta diaria, y muestra un historial con estadísticas.

Está hecha con **Python (Flask)** y **SQLite**, con páginas HTML y JavaScript
sencillo, sin frameworks de frontend.

## Qué puede hacer

| Historia | Qué hace |
|---|---|
| US-001 | Registrar actividades con cronómetro o escribiendo los minutos |
| US-002 | Calcular el consumo en litros (minutos × caudal) |
| US-003 | Detectar excesos de tiempo y de consumo diario (Normal, Precaución, Exceso) |
| US-004 | Alertas en la web y por correo electrónico |
| US-005 y US-006 | Historial, estadísticas, comparativas, ahorro potencial y exportar CSV |
| US-007 | Personalizar caudal y tiempo recomendado de cada actividad |
| US-008 | Configurar la meta diaria y el porcentaje de aviso |
| Extra | Crear actividades propias, con su nombre, caudal y tiempo recomendado |

## Cómo usarlo

Necesitas Python 3.9 o superior.

1. Instala las dependencias:

       pip install -r requirements.txt

2. (Opcional) Configura el correo para las alertas. Mira la sección
   [Alertas por correo](#alertas-por-correo). Sin esto la app funciona igual,
   pero los correos no se envían.

3. Inicia la app:

       python app.py

4. Se abre el navegador en http://localhost:7500. Crea una cuenta, registra una
   actividad en el panel y revisa el historial.

Para apagar el servidor: `Ctrl + C`.

## Actividades propias

En **Configuración → Crear actividad propia** puedes agregar actividades que no
estén en la lista, por ejemplo "Lavar el carro". Se les pone nombre, caudal
(L/min) y tiempo recomendado (minutos). Después aparecen en el cronómetro y en el
selector del panel, y se pueden editar o eliminar desde la misma pantalla.
Al eliminar una actividad, el historial conserva sus registros.

Cada usuario solo ve sus propias actividades, hasta un máximo de 20.

## Alertas por correo

El correo se configura con variables de entorno, nunca dentro del código.
Copia `.env.example` como `.env` y llénalo:

    WCS_SMTP_SERVIDOR=smtp-relay.brevo.com
    WCS_SMTP_PUERTO=587
    WCS_SMTP_USUARIO=tu-usuario-smtp
    WCS_SMTP_CLAVE=tu-clave-smtp
    WCS_SMTP_REMITENTE=correo-verificado-en-el-servicio

Funciona con cualquier servicio SMTP (Brevo, Gmail con contraseña de aplicación,
Mailtrap para pruebas, etc.). El archivo `.env` está en `.gitignore`: **no lo
subas a GitHub**, porque contiene la clave.

Se envía correo cuando el consumo del día llega al porcentaje de aviso de la meta
o la supera. Las alertas por exceso de tiempo en una actividad se muestran solo en
la web. Si el correo falla, la alerta queda guardada de todos modos y se ve en la
pestaña **Alertas**.

## Cómo está organizado

    app.py                 servidor Flask: rutas, cálculos, validaciones y alertas
    db.py                  base de datos SQLite (tablas y consultas)
    correo.py              envío de correos por SMTP
    requirements.txt       dependencias de Python
    .env.example           plantilla de la configuración del correo
    water.db               base de datos (se crea sola, no se sube a GitHub)
    templates/             páginas HTML (login, registro, panel, historial,
                           configuración y alertas)
    static/css/estilos.css estilos
    static/js/panel.js     panel: cronómetro, registro y resumen del día
    static/js/historial.js historial, estadísticas y exportar CSV
    static/js/configuracion.js  meta diaria, caudales, tiempos y actividades propias
    static/js/alertas.js   lista de alertas
    static/js/graficas.js  gráficas SVG
    static/js/menu.js      menú lateral

## Base de datos

SQLite, en el archivo `water.db`. Todas las tablas de datos guardan el `usuario_id`,
así cada persona solo ve y modifica lo suyo:

    usuarios ──< configuracion               meta diaria y % de aviso
             ──< personalizaciones           caudal y tiempo propios de actividades estándar
             ──< actividades_personalizadas  actividades creadas por el usuario
             ──< cronometros                 cronómetro en marcha (máximo uno)
             ──< actividades                 registros de consumo
             ──< alertas                     alertas generadas

Las contraseñas se guardan solo como hash, nunca en texto.

## Versión anterior

Antes el proyecto era una maqueta que guardaba facturas en el `localStorage` del
navegador. Esos archivos siguen en el repositorio pero ya no se usan:
`servidor.py`, `index.html`, `factura.html`, `datos.json` y los scripts
`almacen.js`, `calculos.js`, `factura.js` y `login.js`.