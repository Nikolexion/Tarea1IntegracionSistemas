-- Datos seed de Espacios

------------------------------------------------------------------------------
-- Salas 
------------------------------------------------------------------------------
-- ids explicitos, reservas los guarda
INSERT INTO salas (id, nombre, capacidad) VALUES
    (1, 'Sala 1', 2),
    (2, 'Sala 2', 6),
    (3, 'Sala 3', 10),
    (4, 'Sala 4', 20);

-- Actualiza la secuencia de ids para que no choque con los ids explicitos
SELECT setval(pg_get_serial_sequence('salas', 'id'), (SELECT MAX(id) FROM salas));

------------------------------------------------------------------------------
-- Bloques
------------------------------------------------------------------------------
INSERT INTO bloques (hora_inicio, hora_fin) VALUES
    ('08:00', '09:00'),
    ('09:00', '10:00'),
    ('10:00', '11:00'),
    ('11:00', '12:00'),
    ('12:00', '13:00'),
    ('13:00', '14:00'),
    ('14:00', '15:00'),
    ('15:00', '16:00'),
    ('16:00', '17:00'),
    ('17:00', '18:00'),
    ('18:00', '19:00'),
    ('19:00', '20:00');