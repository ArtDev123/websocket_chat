-- Пользователь и БД для учебного чата на FastAPI + WebSocket.
-- Пароль chat_user должен совпадать с POSTGRES_PASSWORD в .env:
--   POSTGRES_PASSWORD=chat_pass
--
-- Linux:  ./scripts/init_postgres.sh
-- macOS:  ./scripts/init_postgres_mac.sh
-- Windows: powershell -File scripts\init_postgres.ps1

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'chat_user') THEN
        CREATE USER chat_user WITH PASSWORD 'chat_pass';
    ELSE
        ALTER USER chat_user WITH PASSWORD 'chat_pass';
    END IF;
END
$$;

SELECT 'CREATE DATABASE chat_db OWNER chat_user ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'chat_db')\gexec

GRANT ALL PRIVILEGES ON DATABASE chat_db TO chat_user;
ALTER USER chat_user CREATEDB;

\c chat_db

GRANT ALL PRIVILEGES ON SCHEMA public TO chat_user;
GRANT CREATE ON SCHEMA public TO chat_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO chat_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO chat_user;
