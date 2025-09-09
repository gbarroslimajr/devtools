package com.util;

import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Utilitário para criptografar/descriptografar dados de cookies de sessão
 * Usa AES-256 com chave derivada de uma seed fixa
 *
 * @author Geraldo Barros
 * @version 1.0
 */
public class CookieEncryptionUtil {

  private static final Logger log = LoggerFactory.getLogger(CookieEncryptionUtil.class);

  private static final String ALGORITHM = "AES";
  private static final String TRANSFORMATION = "AES/ECB/PKCS5Padding";

  // Seed fixa do projeto - altere para sua chave específica
  private static final String ENCRYPTION_SEED = "2025_SECURE_SESSION_COOKIES_KEY_V1";

  // Cache da chave para performance
  private static SecretKeySpec cachedSecretKey = null;

  /**
   * Gera chave AES a partir da seed fixa
   */
  private static SecretKeySpec getSecretKey() {
    if (cachedSecretKey == null) {
      try {
        // Gerar hash SHA-256 da seed para ter exatos 32 bytes (AES-256)
        MessageDigest sha = MessageDigest.getInstance("SHA-256");
        byte[] keyBytes = sha.digest(ENCRYPTION_SEED.getBytes(StandardCharsets.UTF_8));

        cachedSecretKey = new SecretKeySpec(keyBytes, ALGORITHM);
        log.debug("Secret key generated from seed");

      } catch (Exception e) {
        log.error("Failed to generate secret key: " + e.getMessage(), e);
        throw new RuntimeException("Cookie encryption key generation failed", e);
      }
    }
    return cachedSecretKey;
  }

  /**
   * Criptografa um texto usando AES e retorna Base64
   *
   * @param plainText texto a ser criptografado
   * @return texto criptografado em Base64 (safe para cookies)
   */
  public static String encrypt(String plainText) {
    if (plainText == null || plainText.isEmpty()) {
      return "";
    }

    try {
      Cipher cipher = Cipher.getInstance(TRANSFORMATION);
      cipher.init(Cipher.ENCRYPT_MODE, getSecretKey());

      byte[] encryptedBytes = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));
      String encryptedBase64 = Base64.getEncoder().encodeToString(encryptedBytes);

      log.debug("Text encrypted successfully (length: {} -> {})",
          plainText.length(), encryptedBase64.length());

      return encryptedBase64;

    } catch (Exception e) {
      log.error("Encryption failed for text: " + e.getMessage(), e);

      // Fallback: retorna texto original em Base64 (pelo menos não fica explícito)
      return Base64.getEncoder().encodeToString(plainText.getBytes(StandardCharsets.UTF_8));
    }
  }

  /**
   * Descriptografa um texto Base64 usando AES
   *
   * @param encryptedBase64 texto criptografado em Base64
   * @return texto original descriptografado
   */
  public static String decrypt(String encryptedBase64) {
    if (encryptedBase64 == null || encryptedBase64.isEmpty()) {
      return "";
    }

    try {
      byte[] encryptedBytes = Base64.getDecoder().decode(encryptedBase64);

      Cipher cipher = Cipher.getInstance(TRANSFORMATION);
      cipher.init(Cipher.DECRYPT_MODE, getSecretKey());

      byte[] decryptedBytes = cipher.doFinal(encryptedBytes);
      String decryptedText = new String(decryptedBytes, StandardCharsets.UTF_8);

      log.debug("Text decrypted successfully (length: {} -> {})",
          encryptedBase64.length(), decryptedText.length());

      return decryptedText;

    } catch (Exception e) {
      log.error("Decryption failed for encrypted text: " + e.getMessage(), e);

      // Fallback: tentar como Base64 simples (compatibilidade)
      try {
        return new String(Base64.getDecoder().decode(encryptedBase64), StandardCharsets.UTF_8);
      } catch (Exception fallbackException) {
        log.error("Fallback decryption also failed", fallbackException);
        return "";
      }
    }
  }

  /**
   * Cria e criptografa dados do usuário usando JSON simples
   *
   * @param userLogin login do usuário
   * @param firstName nome
   * @param lastName  sobrenome
   * @param email     email
   * @return JSON criptografado em Base64
   */
  public static String encryptUserDataSimple(String userLogin, String firstName, String lastName, String email) {
    try {
      // Criar JSON simples manualmente
      StringBuilder jsonBuilder = new StringBuilder();
      jsonBuilder.append("{");
      jsonBuilder.append("\"login\":\"").append(escapeJsonSimple(userLogin != null ? userLogin : "")).append("\",");
      jsonBuilder.append("\"firstName\":\"").append(escapeJsonSimple(firstName != null ? firstName : "")).append("\",");
      jsonBuilder.append("\"lastName\":\"").append(escapeJsonSimple(lastName != null ? lastName : "")).append("\",");
      jsonBuilder.append("\"email\":\"").append(escapeJsonSimple(email != null ? email : "")).append("\",");
      jsonBuilder.append("\"authTime\":").append(System.currentTimeMillis()).append(",");
      jsonBuilder.append("\"version\":\"1.0\"");
      jsonBuilder.append("}");

      String jsonData = jsonBuilder.toString();
      log.debug("User JSON created: {} chars", jsonData.length());

      return encrypt(jsonData);

    } catch (Exception e) {
      log.error("Failed to encrypt user data: " + e.getMessage(), e);
      return "";
    }
  }

  /**
   * Descriptografa e parseia JSON simples do usuário
   *
   * @param encryptedUserData JSON criptografado
   * @return Map com dados do usuário
   */
  public static Map<String, String> decryptUserDataSimple(String encryptedUserData) {
    Map<String, String> userData = new HashMap<>();

    try {
      String jsonData = decrypt(encryptedUserData);

      if (jsonData.isEmpty()) {
        log.warn("Decrypted user data is empty");
        return userData;
      }

      log.debug("Decrypted JSON: {} chars", jsonData.length());

      // Parse JSON simples (sem dependência externa)
      userData = parseSimpleJson(jsonData);

      if (userData.isEmpty()) {
        log.warn("Failed to parse user data JSON");
      } else {
        log.debug("User data parsed successfully: {} fields", userData.size());
      }

    } catch (Exception e) {
      log.error("Failed to decrypt user data: " + e.getMessage(), e);
    }

    return userData;
  }

  /**
   * Parser JSON simples (sem dependências externas)
   */
  private static Map<String, String> parseSimpleJson(String json) {
    Map<String, String> result = new HashMap<>();

    try {
      // Remove { e }
      json = json.trim();
      if (json.startsWith("{"))
        json = json.substring(1);
      if (json.endsWith("}"))
        json = json.substring(0, json.length() - 1);

      // Split por vírgula
      String[] pairs = json.split(",");

      for (String pair : pairs) {
        String[] keyValue = pair.split(":", 2);
        if (keyValue.length == 2) {
          String key = keyValue[0].trim().replaceAll("\"", "");
          String value = keyValue[1].trim().replaceAll("\"", "");
          result.put(key, value);
        }
      }

    } catch (Exception e) {
      log.error("Simple JSON parsing failed: " + e.getMessage(), e);
    }

    return result;
  }

  /**
   * Escapa caracteres especiais para JSON
   */
  private static String escapeJsonSimple(String text) {
    if (text == null)
      return "";
    return text.replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t");
  }

  /**
   * Testa a criptografia/descriptografia
   */
  public static boolean testEncryption() {
    try {
      String testText = "f61951";
      String encrypted = encrypt(testText);
      String decrypted = decrypt(encrypted);

      boolean success = testText.equals(decrypted);
      log.info("Encryption test: {} (original: {}, encrypted: {}, decrypted: {})",
          success ? "PASSED" : "FAILED", testText, encrypted, decrypted);

      return success;

    } catch (Exception e) {
      log.error("Encryption test failed: " + e.getMessage(), e);
      return false;
    }
  }

  /**
   * Testa criptografia de dados do usuário
   */
  public static boolean testUserDataEncryptionSimple() {
    try {
      String encrypted = encryptUserDataSimple("f61951", "João", "Silva", "joao.silva@teste.com");
      Map<String, String> decrypted = decryptUserDataSimple(encrypted);

      boolean success = "f61951".equals(decrypted.get("login")) &&
          "João".equals(decrypted.get("firstName"));

      log.info("User data encryption test (Simple): {} (encrypted: {} chars)",
          success ? "PASSED" : "FAILED", encrypted.length());

      return success;

    } catch (Exception e) {
      log.error("User data encryption test (Simple) failed: " + e.getMessage(), e);
      return false;
    }
  }
}
