from app.models.test_ import Test
from app.schemas import test_ as test_schema


def test_test_schemas_expose_only_material_ids_for_material_links():
    assert "material_ids" in test_schema.TestCreate.model_fields
    assert "material_ids" in test_schema.TestUpdate.model_fields
    assert "material_ids" in test_schema.TestRead.model_fields
    assert "material_id" not in test_schema.TestCreate.model_fields
    assert "material_id" not in test_schema.TestUpdate.model_fields
    assert "material_id" not in test_schema.TestRead.model_fields


def test_test_model_has_no_legacy_material_id_column():
    assert "material_id" not in Test.__table__.columns.keys()
    assert "materials" in Test.__mapper__.relationships.keys()
