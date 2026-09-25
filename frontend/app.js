// Frontend mínimo de CoLabora (ADR-021).
// Regla de seguridad (ADR-005): todo dato recibido de la API se muestra con
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

function mostrarMensaje(texto) {
  document.getElementById("mensajes").textContent = texto;
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
}

function cerrarSesion() {
  sessionStorage.removeItem("token");
  document.getElementById("seccion-sesion").hidden = true;
  document.getElementById("seccion-acceso").hidden = false;
}

// ------------------------------------------------------------
// Inicio
// ------------------------------------------------------------

document.getElementById("form-login").addEventListener("submit", iniciarSesion);
document.getElementById("form-registro").addEventListener("submit", registrarse);
document.getElementById("boton-salir").addEventListener("click", cerrarSesion);

// Si la pestaña ya tenía un token (recarga de página), se retoma la sesión
if (sessionStorage.getItem("token")) {
  cargarSesion();
}
