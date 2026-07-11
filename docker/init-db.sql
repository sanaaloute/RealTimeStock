-- Extra databases for the stack. This script runs ONLY on the first
-- initialization of the postgres_data volume (empty data directory).
-- On an existing deployment, create it manually instead:
--   docker compose exec db psql -U brvm -d brvm -c "CREATE DATABASE evolution;"
CREATE DATABASE evolution;
