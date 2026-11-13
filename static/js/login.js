/* login.js — por ahora el inicio de sesión es solo de diseño (demostración):
   guarda el correo en el localStorage y pasa al panel. No valida la contraseña. */

document.getElementById("formulario").addEventListener("submit", function (evento) {
  evento.preventDefault();   // evita que el navegador recargue la página
  Almacen.guardarUsuario({ correo: document.getElementById("correo").value });
  window.location = "panel.html";
});
