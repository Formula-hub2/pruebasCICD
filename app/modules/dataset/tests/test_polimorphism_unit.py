import pytest

from app import db
from app.modules.auth.models import User
from app.modules.dataset.models import DataSet, DSMetaData, PublicationType, UVLDataSet


@pytest.fixture
def setup_polymorphic_data(test_client):
    # Usuario dummy
    user = User(email="poly_test@test.com", password="password")
    db.session.add(user)
    db.session.commit()

    yield user

    # Limpieza ROBUSTA
    # Borramos el usuario. Por cascadeo, se borrarán sus datasets.
    # Si intentamos borrar el dataset a mano a veces SQLAlchemy se lía con la herencia.
    try:
        # Refrescamos la sesión por si acaso
        db.session.expire_all()
        user_to_del = User.query.get(user.id)
        if user_to_del:
            db.session.delete(user_to_del)
            db.session.commit()
    except Exception as e:
        print(f"Error en teardown: {e}")
        db.session.rollback()


def test_create_uvl_dataset_creates_polymorphic_records(test_client, setup_polymorphic_data):
    """
    Prueba CRÍTICA: Verifica que al usar el servicio UVL, se crea
    la estructura de herencia correcta en BD.
    """
    user = setup_polymorphic_data

    # 1. Preparamos metadatos
    ds_meta = DSMetaData(
        title="Polymorphism Test",
        description="Testing inheritance",
        publication_type=PublicationType.JOURNAL_ARTICLE,
        tags="poly",
    )
    db.session.add(ds_meta)
    db.session.commit()

    # 2. Creamos explícitamente un UVLDataSet (usando el modelo, simulando lo que hace el servicio)
    # Nota: En un caso real usaríamos el servicio, pero aquí queremos testear el modelo ORM puro primero.
    uvl_dataset = UVLDataSet(user_id=user.id, ds_meta_data_id=ds_meta.id, download_count=0)
    db.session.add(uvl_dataset)
    db.session.commit()

    dataset_id = uvl_dataset.id

    # 3. LIMPIEZA DE SESIÓN (Obligar a leer de BD)
    db.session.expire_all()

    # --- VERIFICACIONES ---

    # A. Consultar por la clase PADRE (DataSet)
    # SQLAlchemy debería ser listo y devolvernos una instancia de UVLDataSet
    retrieved_parent = DataSet.query.get(dataset_id)
    assert isinstance(retrieved_parent, UVLDataSet), "Error: Al consultar DataSet no devolvió la instancia hija."
    assert retrieved_parent.dataset_type == "uvl_dataset", "Error: El discriminador polimórfico es incorrecto."

    # B. Verificar persistencia física (SQL crudo para no engañarnos con el ORM)
    # Verificamos que existe en la tabla HIJA
    result_child = db.session.execute(
        db.text("SELECT count(*) FROM uvl_dataset WHERE id = :id"), {"id": dataset_id}
    ).scalar()
    assert result_child == 1, "Error Crítico: No se guardó la fila en la tabla uvl_dataset"

    # Verificamos que existe en la tabla PADRE
    result_parent = db.session.execute(
        db.text("SELECT count(*) FROM data_set WHERE id = :id"), {"id": dataset_id}
    ).scalar()
    assert result_parent == 1, "Error Crítico: No se guardó la fila en la tabla data_set"

    print(">>> ÉXITO: La herencia polimórfica funciona correctamente.")
