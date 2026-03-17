from app.core.crypto import encrypt_data, decrypt_data
from app.models.all_models import User
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.orm import sessionmaker

def test_encrypt_decrypt_utility():
    plain_text = "secret_data"
    encrypted = encrypt_data(plain_text)
    assert encrypted != plain_text
    decrypted = decrypt_data(encrypted)
    assert decrypted == plain_text

def test_encrypt_decrypt_none():
    assert encrypt_data(None) is None
    assert decrypt_data(None) is None

def test_user_model_encryption():
    # Setup in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session)

    with SessionLocal() as session:
        user = User(
            email="test@example.com",
            hashed_password="hashed",
            postal_code="H4T1V6",
            household_size=3,
        )
        user.dietary_preferences = ["vegan"]
        user.allergies = ["peanuts"]
        session.add(user)
        session.commit()
        session.refresh(user)

        # Verify decrypted values (automatic via TypeDecorator)
        assert user.postal_code == "H4T1V6"
        assert user.household_size == 3
        assert user.dietary_preferences == ["vegan"]
        assert user.allergies == ["peanuts"]

        # Check raw database values to ensure they are encrypted
        with engine.connect() as conn:
            import sqlalchemy
            result = conn.execute(sqlalchemy.text("SELECT postal_code, household_size, dietary_preferences_json, allergies_json FROM user WHERE email = 'test@example.com'"))
            row = result.fetchone()

            # Row values should be encrypted strings
            assert row[0] != "H4T1V6"
            assert row[1] != "3"
            assert "vegan" not in row[2]
            assert "peanuts" not in row[3]

            # Verify we can decrypt them manually
            assert decrypt_data(row[0]) == "H4T1V6"
            assert decrypt_data(row[1]) == "3"
            assert "vegan" in decrypt_data(row[2])
