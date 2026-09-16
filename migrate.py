import os

from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db


def column_exists(table_name, column_name):
    inspector = inspect(db.engine)

    if not inspector.has_table(table_name):
        return False

    columns = inspector.get_columns(table_name)

    return any(
        column["name"] == column_name
        for column in columns
    )


def add_currency_columns():
    """
    Add the new currency columns to existing tables.

    This migration is safe to run more than once.
    Existing data is preserved.
    """

    # =====================================================
    # USERS TABLE
    # =====================================================

    if not column_exists("users", "currency"):

        print("Adding users.currency...")

        db.session.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN currency VARCHAR(3)
                NOT NULL
                DEFAULT 'KES'
                """
            )
        )

        db.session.commit()

        print("users.currency added.")

    else:

        print(
            "users.currency already exists."
        )


    # =====================================================
    # TRANSACTIONS TABLE
    # =====================================================

    if not column_exists(
        "transactions",
        "currency"
    ):

        print(
            "Adding transactions.currency..."
        )

        db.session.execute(
            text(
                """
                ALTER TABLE transactions
                ADD COLUMN currency VARCHAR(3)
                NOT NULL
                DEFAULT 'KES'
                """
            )
        )

        db.session.commit()

        print(
            "transactions.currency added."
        )

    else:

        print(
            "transactions.currency already exists."
        )


def create_wallet_table():

    print("Checking wallets table...")

    # SQLAlchemy creates the wallets table
    # according to the current models.py.

    db.create_all()

    print("Wallets table checked/created.")


def create_kes_wallets():

    print(
        "Creating KES wallets for existing users..."
    )

    # Find all existing users.

    users = db.session.execute(
        text(
            """
            SELECT id, balance
            FROM users
            """
        )
    ).fetchall()

    created = 0

    for user in users:

        user_id = user[0]
        balance = user[1] or 0

        # Check whether this user already
        # has a KES wallet.

        existing = db.session.execute(
            text(
                """
                SELECT id
                FROM wallets
                WHERE user_id = :user_id
                AND currency = 'KES'
                LIMIT 1
                """
            ),
            {
                "user_id": user_id
            }
        ).first()

        if existing:

            continue

        # Create wallet using the user's
        # existing balance.

        db.session.execute(
            text(
                """
                INSERT INTO wallets
                    (user_id, currency, balance)
                VALUES
                    (:user_id, 'KES', :balance)
                """
            ),
            {
                "user_id": user_id,
                "balance": balance
            }
        )

        created += 1


    db.session.commit()

    print(
        f"Created {created} KES wallet(s)."
    )


def update_existing_transactions():

    print(
        "Updating existing transactions..."
    )

    db.session.execute(
        text(
            """
            UPDATE transactions
            SET currency = 'KES'
            WHERE currency IS NULL
               OR currency = ''
            """
        )
    )

    db.session.commit()

    print(
        "Existing transactions updated."
    )


def update_existing_users():

    print(
        "Updating existing users..."
    )

    db.session.execute(
        text(
            """
            UPDATE users
            SET currency = 'KES'
            WHERE currency IS NULL
               OR currency = ''
            """
        )
    )

    db.session.commit()

    print(
        "Existing users updated."
    )


def run_migration():

    print("")
    print("======================================")
    print(" INVESTMENT PLATFORM DATABASE MIGRATION")
    print("======================================")
    print("")

    add_currency_columns()

    update_existing_users()

    update_existing_transactions()

    create_wallet_table()

    create_kes_wallets()

    print("")
    print("======================================")
    print(" MIGRATION COMPLETED SUCCESSFULLY")
    print("======================================")
    print("")


if __name__ == "__main__":

    app = create_app()

    with app.app_context():

        run_migration(),
