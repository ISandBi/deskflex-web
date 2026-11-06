-- Esquema DeskFlex México (SQLite). Tipos y restricciones pensados para migrar a PostgreSQL.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre        TEXT    NOT NULL,
    correo        TEXT    NOT NULL UNIQUE,
    telefono      TEXT    NOT NULL,
    password_hash TEXT    NOT NULL,
    rol           TEXT    NOT NULL DEFAULT 'cliente' CHECK (rol IN ('cliente','admin')),
    activo        INTEGER NOT NULL DEFAULT 1,
    creado_en     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS espacios (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    numero    INTEGER NOT NULL UNIQUE,
    nombre    TEXT    NOT NULL,
    tipo      TEXT    NOT NULL CHECK (tipo IN ('sala','fijo','hot')),
    capacidad INTEGER NOT NULL DEFAULT 1,
    activo    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reservas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    folio       TEXT    UNIQUE,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    espacio_id  INTEGER NOT NULL REFERENCES espacios(id),
    fecha       TEXT    NOT NULL,              -- YYYY-MM-DD
    hora_inicio INTEGER NOT NULL,              -- 0-23
    hora_fin    INTEGER NOT NULL,              -- 1-24, > hora_inicio
    asiento     INTEGER,                       -- silla dentro de una sala; NULL = espacio/sala completa
    modo        TEXT    NOT NULL CHECK (modo IN ('hora','dia')),
    estado      TEXT    NOT NULL DEFAULT 'confirmada' CHECK (estado IN ('confirmada','cancelada')),
    token       TEXT    NOT NULL UNIQUE,       -- el QR solo contiene este token
    creada_en   TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (hora_fin > hora_inicio)
);
CREATE INDEX IF NOT EXISTS idx_reservas_fecha ON reservas (fecha, estado);
CREATE INDEX IF NOT EXISTS idx_reservas_usuario ON reservas (usuario_id);

CREATE TABLE IF NOT EXISTS accesos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reserva_id  INTEGER REFERENCES reservas(id) ON DELETE SET NULL,
    operador_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    codigo      TEXT,                          -- lo que se escaneó / tecleó
    resultado   TEXT    NOT NULL CHECK (resultado IN ('autorizado','denegado')),
    motivo      TEXT,
    registrado_en TEXT  NOT NULL               -- hora local CDMX 'YYYY-MM-DD HH:MM:SS'
);
CREATE INDEX IF NOT EXISTS idx_accesos_reserva ON accesos (reserva_id, resultado);
