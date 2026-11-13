/* configuracion.js
   Configuración mensual, caudal y tiempo recomendado por actividad,
   meta diaria de consumo y creación de actividades propias.
*/

/* ----- Configuración del límite mensual ----- */
/* Se cambió: el límite mensual en m³ pertenecía a las facturas y se eliminó.
   Este bloque ahora guarda en SQLite (vía Python) el % de aviso de la meta diaria. */
(function () {
  const formulario = document.getElementById("formulario");
  const mensaje = document.getElementById("mensaje");

  // Cargar el porcentaje de aviso guardado en el servidor.
  fetch("/api/estado")
    .then(function (respuesta) { return respuesta.json(); })
    .then(function (estado) {
      if (estado.porcentaje_aviso !== undefined) {
        formulario.aviso.value = estado.porcentaje_aviso;
      }
    })
    .catch(function () {
      mensaje.textContent = "No se pudo cargar el porcentaje de aviso.";
      mensaje.className = "mensaje error";
    });

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();

    const aviso = parseInt(formulario.aviso.value, 10);

    if (!(aviso >= 1 && aviso <= 100)) {
      mensaje.textContent =
        "El porcentaje debe estar entre 1 y 100.";
      mensaje.className = "mensaje error";
      return;
    }

    fetch("/api/porcentaje-aviso", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ porcentaje_aviso: aviso })
    })
      .then(function (respuesta) { return respuesta.json(); })
      .then(function (resultado) {
        if (resultado.ok) {
          mensaje.textContent = "Porcentaje de aviso guardado.";
          mensaje.className = "mensaje";
        } else {
          mensaje.textContent = resultado.error;
          mensaje.className = "mensaje error";
        }
      })
      .catch(function () {
        mensaje.textContent = "No se pudo conectar con Python.";
        mensaje.className = "mensaje error";
      });
  });
})();


/* ----- US-007: Caudal y tiempo recomendado por actividad ----- */
(function () {
  const formulario = document.getElementById("formCaudales");
  const lista = document.getElementById("caudales");
  const mensaje = document.getElementById("mensajeCaudales");

  let catalogo = [];

  function mostrar(texto, esError) {
    mensaje.textContent = texto;
    mensaje.className = "mensaje" + (esError ? " error" : "");
  }

  function cargar() {
    fetch("/api/estado")
      .then(function (respuesta) {
        if (!respuesta.ok) {
          throw new Error("No se pudo obtener la configuración.");
        }
        return respuesta.json();
      })
      .then(function (estado) {
        catalogo = estado.catalogo || [];

        lista.innerHTML = catalogo.map(function (actividad, indice) {
          const id = String(actividad.id);
          const nombre = String(actividad.nombre);

          // true si la creó el usuario (no viene del catálogo estándar).
          const esPropia = actividad.propia === true;

          const caudal = Number(actividad.caudal);
          const caudalEstandar = Number(actividad.caudal_estandar);

          const tiempo = Number(
            actividad.tiempo_recomendado ??
            actividad.tiempo_recomendado_estandar ??
            0
          );

          const tiempoEstandar = Number(
            actividad.tiempo_recomendado_estandar ??
            actividad.tiempo_recomendado ??
            0
          );

          return `
            <div class="tarjeta">
              <h4>
                ${escaparHTML(nombre)}
                ${esPropia
                  ? `<button type="button" class="boton detener"
                       data-eliminar="${escaparHTML(id)}">Eliminar</button>`
                  : ""}
              </h4>

              <label class="campo" for="caudal_${indice}">
                Caudal personalizado (L/min)
                <span class="suave">
                  ${esPropia
                    ? "Actividad propia"
                    : "Estándar: " + caudalEstandar + " L/min"}
                </span>
                <input
                  type="number"
                  id="caudal_${indice}"
                  name="caudal_${indice}"
                  min="0.01"
                  step="0.01"
                  value="${caudal}"
                  required
                >
              </label>

              <label class="campo" for="tiempo_${indice}">
                Tiempo recomendado (minutos)
                <span class="suave">
                  ${esPropia
                    ? "Actividad propia"
                    : "Estándar: " + tiempoEstandar + " minutos"}
                </span>
                <input
                  type="number"
                  id="tiempo_${indice}"
                  name="tiempo_${indice}"
                  min="0.01"
                  max="1440"
                  step="0.01"
                  value="${tiempo}"
                  required
                >
              </label>
            </div>
          `;
        }).join("");

        if (catalogo.length === 0) {
          mostrar("No hay actividades disponibles en el catálogo.", true);
        }
      })
      .catch(function () {
        mostrar(
          "No se pudo conectar con Python. Ejecuta: python app.py",
          true
        );
      });
  }

  // Evita interpretar los nombres de las actividades como HTML.
  function escaparHTML(valor) {
    return String(valor).replace(/[&<>"']/g, function (caracter) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[caracter];
    });
  }

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();

    if (catalogo.length === 0) {
      mostrar("No hay actividades para guardar.", true);
      return;
    }

    // Validar todos los campos antes de enviar cambios.
    for (let i = 0; i < catalogo.length; i++) {
      const caudal = Number(
        formulario.elements["caudal_" + i].value
      );

      const tiempo = Number(
        formulario.elements["tiempo_" + i].value
      );

      if (!Number.isFinite(caudal) || caudal <= 0) {
        mostrar(
          "El caudal de " + catalogo[i].nombre +
          " debe ser un número mayor que cero.",
          true
        );
        return;
      }

      if (!Number.isFinite(tiempo) || tiempo <= 0 || tiempo > 1440) {
        mostrar(
          "El tiempo recomendado de " + catalogo[i].nombre +
          " debe ser mayor que cero y no superar 1440 minutos.",
          true
        );
        return;
      }
    }

    const envios = [];

    catalogo.forEach(function (actividad, indice) {
      const caudal = formulario.elements["caudal_" + indice].value;
      const tiempo = formulario.elements["tiempo_" + indice].value;

      envios.push(
        enviarConfiguracion("/api/caudal", {
          actividad: actividad.id,
          caudal: caudal
        }).then(function (resultado) {
          if (!resultado.ok) {
            throw new Error(
              actividad.nombre + " (caudal): " + resultado.error
            );
          }
        })
      );

      envios.push(
        enviarConfiguracion("/api/tiempo-recomendado", {
          actividad: actividad.id,
          tiempo_recomendado: tiempo
        }).then(function (resultado) {
          if (!resultado.ok) {
            throw new Error(
              actividad.nombre + " (tiempo): " + resultado.error
            );
          }
        })
      );
    });

    mostrar("Guardando configuración...", false);

    Promise.all(envios)
      .then(function () {
        mostrar("Caudales y tiempos recomendados guardados.", false);
        cargar();
      })
      .catch(function (error) {
        mostrar(
          error.message || "No se pudo guardar la configuración.",
          true
        );
        cargar();
      });
  });

  function enviarConfiguracion(ruta, datos) {
    return fetch(ruta, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(datos)
    }).then(function (respuesta) {
      return respuesta.json().then(function (resultado) {
        if (!respuesta.ok && resultado.ok !== false) {
          resultado.ok = false;
          resultado.error = resultado.error || "Error al guardar.";
        }
        return resultado;
      });
    });
  }

  // Refresca la lista cuando se crea una actividad nueva.
  document.addEventListener("actividades:cambio", cargar);

  // Botón Eliminar de las actividades propias.
  lista.addEventListener("click", function (evento) {
    const boton = evento.target.closest("[data-eliminar]");
    if (!boton) return;

    if (!confirm("¿Eliminar esta actividad? Tu historial se conserva.")) {
      return;
    }

    enviarConfiguracion("/api/actividad-personalizada/eliminar", {
      actividad: boton.dataset.eliminar
    }).then(function (resultado) {
      mostrar(
        resultado.ok ? "Actividad eliminada." : resultado.error,
        !resultado.ok
      );
      cargar();
    });
  });

  cargar();
})();


/* ----- US-008: Meta diaria de consumo ----- */
(function () {
  const formulario = document.getElementById("formMetaDiaria");
  const entrada = document.getElementById("metaDiaria");
  const mensaje = document.getElementById("mensajeMetaDiaria");

  function mostrar(texto, esError) {
    mensaje.textContent = texto;
    mensaje.className = "mensaje" + (esError ? " error" : "");
  }

  // Cargar la meta diaria que está guardada en el servidor.
  function cargarMeta() {
    fetch("/api/estado")
      .then(function (respuesta) {
        if (!respuesta.ok) {
          throw new Error("No se pudo obtener la meta diaria.");
        }
        return respuesta.json();
      })
      .then(function (estado) {
        if (estado.meta_diaria !== undefined &&
            estado.meta_diaria !== null) {
          entrada.value = estado.meta_diaria;
        }
      })
      .catch(function () {
        mostrar(
          "No se pudo cargar la meta diaria. Comprueba que Python esté ejecutándose.",
          true
        );
      });
  }

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();

    const meta = Number(entrada.value);

    if (!Number.isFinite(meta) || meta <= 0) {
      mostrar("La meta diaria debe ser un número mayor que cero.", true);
      return;
    }

    mostrar("Guardando meta diaria...", false);

    fetch("/api/meta-diaria", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        meta_diaria: meta
      })
    })
      .then(function (respuesta) {
        return respuesta.json().then(function (resultado) {
          if (!respuesta.ok || resultado.ok === false) {
            throw new Error(
              resultado.error || "No se pudo guardar la meta diaria."
            );
          }
          return resultado;
        });
      })
      .then(function () {
        mostrar("Meta diaria guardada correctamente.", false);
        cargarMeta();
      })
      .catch(function (error) {
        mostrar(
          error.message || "No se pudo conectar con Python.",
          true
        );
      });
  });

  cargarMeta();
})();


/* ----- Crear actividad propia ----- */
(function () {
  const formulario = document.getElementById("formNuevaActividad");
  const mensaje = document.getElementById("mensajeNuevaActividad");

  function mostrar(texto, esError) {
    mensaje.textContent = texto;
    mensaje.className = "mensaje" + (esError ? " error" : "");
  }

  formulario.addEventListener("submit", function (evento) {
    evento.preventDefault();
    mostrar("Creando actividad...", false);

    fetch("/api/actividad-personalizada", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nombre: formulario.elements["nueva_nombre"].value.trim(),
        caudal: formulario.elements["nueva_caudal"].value,
        tiempo_recomendado: formulario.elements["nueva_tiempo"].value
      })
    })
      .then(function (respuesta) { return respuesta.json(); })
      .then(function (resultado) {
        if (!resultado.ok) {
          throw new Error(resultado.error || "No se pudo crear la actividad.");
        }
        formulario.reset();
        mostrar("Actividad creada. Ya la puedes usar en el panel.", false);
        document.dispatchEvent(new Event("actividades:cambio"));
      })
      .catch(function (error) {
        mostrar(error.message || "No se pudo conectar con Python.", true);
      });
  });
})();