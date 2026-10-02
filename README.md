# Water Controller Smart

Maqueta funcional del diseño (login, panel, historial y configuración de alertas),
con una pantalla para agregar facturas. Es una demostración.

## Cómo usarlo
Solo necesitas Python instalado (no hay que instalar nada más):

    python servidor.py

Se abre el navegador en http://localhost:8000. Entra con cualquier correo, ve a
**Agregar factura**, escribe el mes, el consumo y el total, y guarda. Luego mira el panel.
Para apagar el servidor: Ctrl + C.

## Qué hace Python
`servidor.py` hace dos cosas con librerías que ya vienen con Python:
1. Muestra las páginas del proyecto.
2. Recibe la factura que escribe el usuario y **la revisa** (mes válido, números no negativos).
   Si hay un error, le dice a la página qué corregir.

## Cómo viaja una factura
    formulario -> Python revisa (servidor.py) -> si está bien, se guarda en el localStorage -> panel e historial la muestran

## Archivos
    servidor.py           (Python) servidor y validación de la factura
    index.html            inicio de sesión (solo de diseño)
    panel.html            resumen, alerta y gráficas
    historial.html        tabla, gráfica y exportar CSV
    factura.html          formulario para agregar facturas
    configuracion.html    límite mensual y porcentaje de aviso
    css/estilos.css       estilos
    js/almacen.js         localStorage (solo para demostración)
    js/calculos.js        estado Normal/Precaución/Exceso, promedio, formatos
    js/graficas.js        gráficas SVG
    js/menu.js            menú lateral
    js/factura.js, panel.js, historial.js, configuracion.js, login.js   un script por pantalla

## Nota
El localStorage es solo para demostración: guarda los datos en el navegador de cada
persona. Más adelante se puede cambiar por una base de datos.
