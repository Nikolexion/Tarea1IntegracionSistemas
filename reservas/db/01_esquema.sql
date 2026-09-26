-- Esquema de la base de Reservas
--
-- PostgreSQL lo ejecuta solo al crear la base por primera vez
-- (docker-entrypoint-initdb.d). Cambiarlo exige recrear el volumen
-- Convenciones: ids BIGSERIAL, fechas timestamptz, estados como
-- texto con CHECK en lugar de ENUM (más fácil de evolucionar)
-- 



-- Cuentas de la API. La contraseña se guarda solo como hash bcrypt
-- El email se guarda en minúsculas para que la unicidad no dependa de mayúsculas: el CHECK rechaza cualquier inserción que no lo normalice
CREATE TABLE usuarios (
    id            BIGSERIAL   PRIMARY KEY,
    nombre        TEXT        NOT NULL,
    email         TEXT        NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash TEXT        NOT NULL,
    rol           TEXT        NOT NULL CHECK (rol IN ('usuario', 'administrador')),
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Una reserva nunca se borra: al cancelarla pasa a CANCELADA
CREATE TABLE reservas (
    id            BIGSERIAL   PRIMARY KEY,
    -- Referencia de la ocupación en Espacios. La genera Reservas antes de
    -- guardar la reserva, para poder compensar aunque nunca llegue a guardarse
    referencia    UUID        NOT NULL UNIQUE,
    estado        TEXT        NOT NULL CHECK (estado IN ('ACTIVA', 'CANCELADA')),
    -- Sin llave foránea: la sala vive en la base de Espacios
    sala_id       BIGINT      NOT NULL,
    sala_nombre   TEXT        NOT NULL,
    fecha         DATE        NOT NULL,
    hora_inicio   TIME        NOT NULL,
    hora_fin      TIME        NOT NULL,
    titular_id    BIGINT      NOT NULL REFERENCES usuarios (id),
    creada_por_id BIGINT      NOT NULL REFERENCES usuarios (id),
    creada_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelada_en  TIMESTAMPTZ NULL
);

-- "Mis reservas" filtra por titular y ordena por fecha de creación
CREATE INDEX reservas_titular_idx ON reservas (titular_id, creada_en DESC);


CREATE INDEX reservas_creada_en_idx ON reservas (creada_en DESC);


-- Respuesta guardada por cada Idempotency-Key de POST /v1/reservas
-- El alcance es por usuario: la misma clave de dos usuarios no choca
-- EN_CURSO: la primera petición aún no termina (un reintento recibe 409)
-- COMPLETADA: se guardó la respuesta y se repite tal cual
-- hash_cuerpo permite detectar la misma clave con otro cuerpo (422)
CREATE TABLE claves_idempotencia (
    usuario_id       BIGINT      NOT NULL REFERENCES usuarios (id),
    clave            TEXT        NOT NULL,
    hash_cuerpo      TEXT        NOT NULL,
    estado           TEXT        NOT NULL CHECK (estado IN ('EN_CURSO', 'COMPLETADA')),
    codigo_http      INT         NULL,
    cuerpo_respuesta JSONB       NULL,
    creada_en        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (usuario_id, clave)
);


-- Cola de LiberarPuesto por enviar a Espacios. Se inserta en la misma transacción que cancela la reserva, una tarea en segundo plano la procesa y borra cada fila al tener éxito
-- La referencia no apunta a reservas: también se encolan ocupaciones cuya reserva nunca se guardó (timeout o falla al guardar)
CREATE TABLE liberaciones_pendientes (
    id           BIGSERIAL   PRIMARY KEY,
    referencia   UUID        NOT NULL,
    -- Sala y franja sirven para invalidar la caché de disponibilidad cuando el puesto se libera efectivamente
    sala_id      BIGINT      NOT NULL,
    fecha        DATE        NOT NULL,
    hora_inicio  TIME        NOT NULL,
    hora_fin     TIME        NOT NULL,
    intentos     INT         NOT NULL DEFAULT 0,
    ultimo_error TEXT        NULL,
    creada_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);
