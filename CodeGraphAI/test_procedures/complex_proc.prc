CREATE OR REPLACE PROCEDURE complex_proc(
    p_id IN NUMBER,
    p_name OUT VARCHAR2,
    p_status INOUT VARCHAR2
) AS
    v_count NUMBER;
    v_result VARCHAR2(100);
BEGIN
    -- Multiple IF statements
    IF p_id > 0 THEN
        SELECT COUNT(*) INTO v_count FROM orders WHERE customer_id = p_id;

        IF v_count > 10 THEN
            p_status := 'VIP';
        ELSE
            p_status := 'REGULAR';
        END IF;
    END IF;

    -- Cursor usage
    DECLARE
        CURSOR c_orders IS
            SELECT * FROM orders WHERE customer_id = p_id;
    BEGIN
        FOR rec IN c_orders LOOP
            INSERT INTO order_history VALUES (rec.id, rec.total);
        END LOOP;
    END;

    -- Exception handling
    BEGIN
        UPDATE customers SET last_order_date = SYSDATE WHERE id = p_id;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20001, 'Customer not found');
    END;

    p_name := 'Processed';
END;

