# Database setup

All tables live in the `aria` schema (PostgreSQL).

## Setup
1. Install PostgreSQL and pgAdmin.
2. Run the schema script:

       psql -U postgres -h localhost -d postgres -f app/db/migrations/001_create_aria_schema.sql

   Or open pgAdmin's Query Tool, paste the contents of the file and press F5.
3. Copy `Agent/backend/.env.example` to `Agent/backend/.env` and put in your own password.

## Using the tables
Write `aria.users`, or set `search_path=aria` on the connection.

## Changing the schema
Never edit an existing migration. Add a new numbered file
(`002_add_xyz.sql`) and open a PR.