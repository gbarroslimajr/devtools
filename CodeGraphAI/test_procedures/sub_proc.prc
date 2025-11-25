CREATE OR REPLACE PROCEDURE sub_proc AS
BEGIN
    IF EXISTS(SELECT 1 FROM products) THEN
        SELECT * FROM products WHERE active = 1;
    END IF;

    LOOP
        FETCH cursor_products INTO v_product;
        EXIT WHEN cursor_products%NOTFOUND;
    END LOOP;
END;

