// Frontend mínimo de CoLabora.
// Regla de seguridad: todo dato recibido de la API se muestra con
// textContent, nunca con innerHTML.

// ------------------------------------------------------------
// Llamada a la API
// ------------------------------------------------------------

// Hace una petición a la API y devuelve el JSON de la respuesta.
// Si la respuesta es un error, muestra el Problem Details y devuelve null.
async function llamarApi(metodo, ruta, cuerpo, cabecerasExtra) {
  const cabeceras = Object.assign({}, cabecerasExtra);
  const token = sessionStorage.getItem("token");
  if (token) {
    cabeceras["Authorization"] = "Bearer " + token;
  }
  const opciones = { method: metodo, headers: cabeceras };
  if (cuerpo !== undefined) {
    if (!cabeceras["Content-Type"]) {
      cabeceras["Content-Type"] = "application/json";
    }
    opciones.body = JSON.stringify(cuerpo);
  }

  let respuesta;
  try {
    respuesta = await fetch(ruta, opciones);
  } catch (error) {
    mostrarMensaje("No se pudo conectar con el servidor.");
    return null;
  }

  // Si el cuerpo no es JSON (por ejemplo, un error de nginx), se trata como vacío
  const datos = await respuesta.json().catch(function () { return null; });
  if (!respuesta.ok) {
    if (datos && datos.title) {
      mostrarMensaje("Error " + respuesta.status + ": " + datos.title +
        (datos.detail ? " — " + datos.detail : ""));
    } else {
      mostrarMensaje("Error " + respuesta.status + ".");
    }
    return null;
  }
  return datos;
}

// Ejecuta un enlace HATEOAS tal como lo entrega el servidor
function seguirEnlace(enlace, cabecerasExtra) {
  return llamarApi(enlace.method, enlace.href, enlace.body, cabecerasExtra);
}

function mostrarMensaje(texto) {
  document.getElementById("mensajes").textContent = texto;
}

// ------------------------------------------------------------
// Ayudas para construir tablas
// ------------------------------------------------------------

function agregarCelda(fila, texto) {
  const celda = document.createElement("td");
  celda.textContent = texto;
  fila.appendChild(celda);
  return celda;
}

function agregarBoton(celda, texto, alHacerClic) {
  const boton = document.createElement("button");
  boton.textContent = texto;
  boton.addEventListener("click", alHacerClic);
  celda.appendChild(boton);
}

// Muestra una página de un listado. Si la respuesta trae el enlace "siguiente", el botón
// "Ver más" lo sigue: la interfaz no calcula páginas, usa las que ofrece la API.
function mostrarPagina(lista, idTabla, idBoton, crearFila, agregarAlFinal) {
  const tabla = document.getElementById(idTabla);
  if (!agregarAlFinal) {
    tabla.replaceChildren();
  }
  for (const elemento of lista.items) {
    tabla.appendChild(crearFila(elemento));
  }
  const boton = document.getElementById(idBoton);
  const siguiente = lista._links && lista._links.siguiente;
  boton.hidden = !siguiente;
  boton.onclick = async function () {
    const pagina = await seguirEnlace(siguiente);
    if (pagina) {
      mostrarPagina(pagina, idTabla, idBoton, crearFila, true);
    }
  };
}

// ------------------------------------------------------------
// Sesión
// ------------------------------------------------------------

async function iniciarSesion(evento) {
  evento.preventDefault();
  const formulario = evento.target;
  const token = await llamarApi("POST", "/v1/auth/login", {
    email: formulario.email.value,
    password: formulario.password.value,
  });
  if (!token) {
    return;
  }
  sessionStorage.setItem("token", token.access_token);
  formulario.reset();
  mostrarMensaje("");
  await cargarSesion();
}

async function registrarse(evento) {
  evento.preventDefault();
  const formulario = evento.target;
  const usuario = await llamarApi("POST", "/v1/usuarios", {
    nombre: formulario.nombre.value,
    email: formulario.email.value,
    password: formulario.password.value,
  });
  if (!usuario) {
    return;
  }
  formulario.reset();
  mostrarMensaje("Cuenta creada para " + usuario.email + ". Ya puede iniciar sesión.");
}

// Carga los datos del usuario del token y muestra la parte con sesión
async function cargarSesion() {
  const usuario = await llamarApi("GET", "/v1/usuarios/me");
  if (!usuario) {
    // Token vencido o inválido: se descarta y se vuelve al formulario de acceso
    cerrarSesion();
    return;
  }
  document.getElementById("sesion-nombre").textContent = usuario.nombre;
  document.getElementById("sesion-rol").textContent = usuario.rol;
  document.getElementById("seccion-acceso").hidden = true;
  document.getElementById("seccion-sesion").hidden = false;

  const esAdministrador = usuario.rol === "administrador";
  document.getElementById("seccion-usuarios").hidden = !esAdministrador;
  // Un administrador ve todas las reservas, no solo las suyas
  document.getElementById("titulo-reservas").textContent =
    esAdministrador ? "Todas las reservas" : "Mis reservas";

  await cargarReservas();
  if (esAdministrador) {
    await cargarUsuarios();
  }
}

function cerrarSesion() {
  sessionStorage.removeItem("token");
  document.getElementById("seccion-sesion").hidden = true;
  document.getElementById("seccion-usuarios").hidden = true;
  document.getElementById("seccion-acceso").hidden = false;
  document.getElementById("filtro-salas").replaceChildren();
  document.getElementById("tabla-grilla").replaceChildren();
  document.getElementById("tabla-reservas").replaceChildren();
  document.getElementById("tabla-usuarios").replaceChildren();
}

// ------------------------------------------------------------
// Grilla de disponibilidad
// ------------------------------------------------------------

// Última grilla cargada: los botones de sala la filtran sin volver a llamar a la API
let grillaActual = null;
// Sala elegida (null = todas); se conserva al recargar la grilla
let salaElegida;

async function cargarGrilla() {
  const fecha = document.getElementById("fecha").value;
  if (!fecha) {
    mostrarMensaje("Elija una fecha.");
    return;
  }
  const grilla = await llamarApi("GET", "/v1/salas?fecha=" + encodeURIComponent(fecha));
  if (!grilla) {
    return;
  }
  grillaActual = grilla;
  crearFiltroSalas(grilla.salas);
  const sigueExistiendo = grilla.salas.some(function (sala) { return sala.id === salaElegida; });
  if (salaElegida === null || sigueExistiendo) {
    mostrarGrilla(salaElegida);
  } else {
    // Por defecto se muestra la primera sala: todas juntas son demasiadas filas
    mostrarGrilla(grilla.salas.length > 0 ? grilla.salas[0].id : null);
  }
}

// Un botón por cada sala que trae la respuesta (no fijos) y uno para verlas todas
function crearFiltroSalas(salas) {
  const filtro = document.getElementById("filtro-salas");
  filtro.replaceChildren();
  agregarBoton(filtro, "Todas", function () {
    mostrarGrilla(null);
  });
  for (const sala of salas) {
    agregarBoton(filtro, sala.nombre, function () {
      mostrarGrilla(sala.id);
    });
  }
}

// Muestra las franjas de una sala (o de todas si salaId es null), ordenadas por hora
function mostrarGrilla(salaId) {
  salaElegida = salaId;
  const tabla = document.getElementById("tabla-grilla");
  tabla.replaceChildren();
  for (const sala of grillaActual.salas) {
    if (salaId !== null && sala.id !== salaId) {
      continue;
    }
    const franjas = sala.franjas.slice().sort(function (a, b) {
      return a.hora_inicio.localeCompare(b.hora_inicio);
    });
    for (const franja of franjas) {
      const fila = document.createElement("tr");
      agregarCelda(fila, sala.nombre);
      agregarCelda(fila, franja.hora_inicio + "–" + franja.hora_fin);
      agregarCelda(fila, franja.puestos_libres + " de " + sala.capacidad);
      const celdaAccion = agregarCelda(fila, "");
      // El botón aparece solo si el servidor ofrece la acción
      const enlaceReservar = franja._links && franja._links.reservar;
      if (enlaceReservar) {
        agregarBoton(celdaAccion, "Reservar", function () {
          reservar(enlaceReservar);
        });
      }
      tabla.appendChild(fila);
    }
  }
}

async function reservar(enlace) {
  // Clave nueva en cada clic: un reintento del mismo clic no duplica la reserva
  const reserva = await seguirEnlace(enlace, { "Idempotency-Key": crypto.randomUUID() });
  if (!reserva) {
    return;
  }
  mostrarMensaje("Reserva " + reserva.id + " creada en " + reserva.sala_nombre + ".");
  await cargarGrilla();
  await cargarReservas();
}

// ------------------------------------------------------------
// Mis reservas
// ------------------------------------------------------------

async function cargarReservas() {
  const lista = await llamarApi("GET", "/v1/reservas");
  if (lista) {
    mostrarPagina(lista, "tabla-reservas", "mas-reservas", filaReserva, false);
  }
}

function filaReserva(reserva) {
  const fila = document.createElement("tr");
  agregarCelda(fila, reserva.id);
  agregarCelda(fila, reserva.sala_nombre);
  agregarCelda(fila, reserva.fecha);
  agregarCelda(fila, reserva.hora_inicio + "–" + reserva.hora_fin);
  agregarCelda(fila, reserva.estado);
  const celdaAccion = agregarCelda(fila, "");
  const enlaceCancelar = reserva._links && reserva._links.cancelar;
  if (enlaceCancelar) {
    agregarBoton(celdaAccion, "Cancelar", function () {
      cancelar(enlaceCancelar);
    });
  }
  return fila;
}

async function cancelar(enlace) {
  const reserva = await seguirEnlace(enlace, { "Content-Type": "application/merge-patch+json" });
  if (!reserva) {
    return;
  }
  mostrarMensaje("Reserva " + reserva.id + " cancelada.");
  await cargarReservas();
}

// ------------------------------------------------------------
// Usuarios (solo administradores)
// ------------------------------------------------------------

async function cargarUsuarios() {
  const lista = await llamarApi("GET", "/v1/usuarios");
  if (lista) {
    mostrarPagina(lista, "tabla-usuarios", "mas-usuarios", filaUsuario, false);
  }
}

function filaUsuario(usuario) {
  const fila = document.createElement("tr");
  agregarCelda(fila, usuario.id);
  agregarCelda(fila, usuario.nombre);
  agregarCelda(fila, usuario.email);
  agregarCelda(fila, usuario.rol);
  return fila;
}

// ------------------------------------------------------------
// Inicio
// ------------------------------------------------------------

document.getElementById("form-login").addEventListener("submit", iniciarSesion);
document.getElementById("form-registro").addEventListener("submit", registrarse);
document.getElementById("boton-salir").addEventListener("click", cerrarSesion);
document.getElementById("boton-grilla").addEventListener("click", cargarGrilla);
document.getElementById("boton-reservas").addEventListener("click", cargarReservas);
document.getElementById("boton-usuarios").addEventListener("click", cargarUsuarios);

// Si la pestaña ya tenía un token (recarga de página), se retoma la sesión
if (sessionStorage.getItem("token")) {
  cargarSesion();
}
