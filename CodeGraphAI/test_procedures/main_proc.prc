CREATE OR REPLACE PROCEDURE main_proc AS
BEGIN
    CALL sub_proc();
    SELECT * FROM orders;
    UPDATE products SET status = 'active' WHERE id > 0;
    DELETE FROM temp_table WHERE processed = 1;
END;

