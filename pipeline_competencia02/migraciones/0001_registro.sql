-- Registro de corridas: tablas de escritura (diseño, decisión 5). Un esquema por entorno.
-- Solo se agrega; lo único que se actualiza es el estado, el fin y el latido de corridas y etapas, y el estado de
-- la publicación. Las horas van con zona (timestamptz) y el latido se compara con el reloj de la base.

CREATE TABLE corrida (
    id                 bigserial PRIMARY KEY,
    tipo               text NOT NULL CHECK (tipo IN ('mensual', 'fabrica', 'medicion', 'prueba')),
    mes                integer,
    estado             text NOT NULL DEFAULT 'en_curso'
                       CHECK (estado IN ('en_curso', 'completada', 'fallida', 'rechazada', 'interrumpida', 'reemplazada')),
    quien              text NOT NULL,
    maquina            text NOT NULL,
    pid                integer NOT NULL,
    proceso_creado     timestamptz,
    commit_git         text,
    cambios_sin_commit boolean,
    huella_catalogo    text,
    huella_config      text,
    huella_entrada     text,
    version_python     text,
    paquetes           jsonb,
    inicio             timestamptz NOT NULL DEFAULT now(),
    latido             timestamptz NOT NULL DEFAULT now(),
    fin                timestamptz,
    motivo             text,
    codigo_salida      integer
);
-- a lo sumo una corrida mensual en curso por mes (el esquema ya es el del entorno)
CREATE UNIQUE INDEX corrida_una_en_curso_por_mes ON corrida (mes) WHERE estado = 'en_curso' AND tipo = 'mensual';
CREATE INDEX corrida_por_mes ON corrida (mes, id);

CREATE TABLE etapa (
    id              bigserial PRIMARY KEY,
    corrida_id      bigint NOT NULL REFERENCES corrida (id),
    orden           integer NOT NULL,
    nombre          text NOT NULL,
    estado          text NOT NULL CHECK (estado IN ('en_curso', 'completada', 'fallida', 'omitida')),
    inicio          timestamptz,
    fin             timestamptz,
    filas           bigint,
    pico_memoria_mb integer,
    error           text,
    traza           text,
    UNIQUE (corrida_id, nombre)
);

CREATE TABLE evento (
    id          bigserial PRIMARY KEY,
    corrida_id  bigint NOT NULL REFERENCES corrida (id),
    etapa       text,
    hora        timestamptz NOT NULL DEFAULT now(),
    nivel       text NOT NULL CHECK (nivel IN ('info', 'aviso', 'error')),
    regla       text,
    mensaje     text NOT NULL,
    datos       jsonb
);
CREATE INDEX evento_por_corrida ON evento (corrida_id, id);

CREATE TABLE control_calidad (
    corrida_id     bigint NOT NULL REFERENCES corrida (id),
    mes            integer NOT NULL,
    variable       text NOT NULL,
    prop_ceros     double precision,
    prop_faltantes double precision,
    psi            double precision,
    decision       text NOT NULL,
    PRIMARY KEY (corrida_id, variable)
);

CREATE TABLE envios (
    corrida_id          bigint NOT NULL REFERENCES corrida (id),
    mes                 integer NOT NULL,
    estrategia          text NOT NULL,
    rol                 text NOT NULL,
    cantidad            integer NOT NULL,
    corte               double precision NOT NULL,
    probabilidad_minima double precision,
    PRIMARY KEY (corrida_id, estrategia)
);

CREATE TABLE publicacion (
    corrida_id        bigint PRIMARY KEY REFERENCES corrida (id),
    mes               integer NOT NULL,
    estado            text NOT NULL CHECK (estado IN ('publicando', 'publicado')),
    sha256_salida     text NOT NULL,
    sha256_historia   text NOT NULL,
    sha256_decisiones text NOT NULL,
    creada            timestamptz NOT NULL DEFAULT now(),
    publicada         timestamptz
);
CREATE INDEX publicacion_por_mes ON publicacion (mes);

CREATE TABLE medicion_eventual (
    id         bigserial PRIMARY KEY,
    corrida_id bigint REFERENCES corrida (id),
    mes        integer NOT NULL,
    motivo     text NOT NULL,
    quien      text NOT NULL,
    hora       timestamptz NOT NULL DEFAULT now()
);
