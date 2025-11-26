import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorageService {
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  // Key constants
  static const String _emailKey = 'user_email';
  static const String _passwordKey = 'user_password';
  static const String _cookieKey = 'user_cookie';

  // Save email
  Future<void> saveEmail(String email) async {
    await _storage.write(key: _emailKey, value: email);
  }

  // Get email
  Future<String?> getEmail() async {
    return await _storage.read(key: _emailKey);
  }

  // Save password
  Future<void> savePassword(String password) async {
    await _storage.write(key: _passwordKey, value: password);
  }

  // Get password
  Future<String?> getPassword() async {
    return await _storage.read(key: _passwordKey);
  }

  // Save cookie
  Future<void> saveCookie(String cookie) async {
    await _storage.write(key: _cookieKey, value: cookie);
  }

  // Get cookie
  Future<String?> getCookie() async {
    return await _storage.read(key: _cookieKey);
  }

  // Save all credentials at once
  Future<void> saveCredentials({
    required String email,
    required String password,
    String? cookie,
  }) async {
    await saveEmail(email);
    await savePassword(password);
    if (cookie != null) {
      await saveCookie(cookie);
    }
  }

  // Get all credentials at once
  Future<Map<String, String?>> getCredentials() async {
    final email = await getEmail();
    final password = await getPassword();
    final cookie = await getCookie();

    return {'email': email, 'password': password, 'cookie': cookie};
  }

  // Delete a specific key
  Future<void> delete(String key) async {
    await _storage.delete(key: key);
  }

  // Clear all stored data
  Future<void> clearAll() async {
    await _storage.deleteAll();
  }
}
