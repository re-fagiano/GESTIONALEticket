-- Aggiunge il codice cliente di 4 caratteri e popola i valori esistenti.
ALTER TABLE customers ADD COLUMN code TEXT;

WITH ordered AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY id) - 1 AS rn
    FROM customers
)
UPDATE customers
SET code = (
    SELECT char(
        97 + ((rn / 17576) % 26),
        97 + ((rn / 676) % 26),
        97 + ((rn / 26) % 26),
        97 + (rn % 26)
    )
    FROM ordered
    WHERE ordered.id = customers.id
)
WHERE code IS NULL OR code = '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_code ON customers(code);
