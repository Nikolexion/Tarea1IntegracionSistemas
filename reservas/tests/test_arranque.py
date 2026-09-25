from app.auth.contrasenas import verificar_contrasena
from app.dominio.usuarios import crear_administrador_inicial


async def test_administrador_inicial_se_crea_una_sola_vez_con_hash_bcrypt(conexion_prueba):
    await conexion_prueba.execute("UPDATE usuarios SET rol = 'usuario' WHERE rol = 'administrador'")

    for _ in range(2):  # dos arranques seguidos
        await crear_administrador_inicial(conexion_prueba, "Admin@Prueba.Test", "clave-admin")

    cursor = await conexion_prueba.execute(
        "SELECT email, password_hash FROM usuarios WHERE rol = 'administrador'"
    )
    [(email, password_hash)] = await cursor.fetchall()
    assert email == "admin@prueba.test"
    assert password_hash.startswith("$2b$")
    assert await verificar_contrasena("clave-admin", password_hash)
