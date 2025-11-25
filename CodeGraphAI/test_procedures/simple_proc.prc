CREATE OR REPLACE PROCEDURE simple_proc AS
BEGIN
    SELECT * FROM users;
    INSERT INTO logs (message, created_at) VALUES ('executed', SYSDATE);
END;

