CREATE TABLE usuarios (
    id            BIGSERIAL   PRIMARY KEY,
    nombre        TEXT        NOT NULL,
    email         TEXT        NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash TEXT        NOT NULL,
    rol           TEXT        NOT NULL CHECK (rol IN ('usuario', 'administrador')),
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Una reserva nunca se borra
CREATE TABLE reservas (
    id            BIGSERIAL   PRIMARY KEY,
    referencia    UUID        NOT NULL UNIQUE,
    estado        TEXT        NOT NULL CHECK (estado IN ('ACTIVA', 'CANCELADA')),
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

CREATE INDEX reservas_titular_idx ON reservas (titular_id, creada_en DESC);

CREATE INDEX reservas_creada_en_idx ON reservas (creada_en DESC);

CREATE TABLE liberaciones_pendientes (
    id           BIGSERIAL   PRIMARY KEY,
    referencia   UUID        NOT NULL,
    sala_id      BIGINT      NOT NULL,
    fecha        DATE        NOT NULL,
    hora_inicio  TIME        NOT NULL,
    hora_fin     TIME        NOT NULL,
    intentos     INT         NOT NULL DEFAULT 0,
    ultimo_error TEXT        NULL,
    creada_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);
