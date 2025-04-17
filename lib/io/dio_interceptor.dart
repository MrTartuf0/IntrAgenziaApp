import 'package:dio/dio.dart';
import 'package:intr_agenzia_app/io/secure_storage_handler.dart';

class CookieInterceptor extends Interceptor {
  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    try {
      // Recupera il cookie salvato nel SecureStorageService
      final cookie = await SecureStorageService().getCookie();

      if (cookie != null && cookie.isNotEmpty) {
        // Aggiungi il cookie agli headers
        options.headers['Cookie'] = cookie;
      }
    } catch (e) {
      // Gestisci eventuali errori nel recupero del cookie
      print('Errore nel recupero del cookie: $e');
    }

    // Continua con la richiesta
    super.onRequest(options, handler);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    // Gestione opzionale della risposta
    super.onResponse(response, handler);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    // Gestione opzionale degli errori
    super.onError(err, handler);
  }
}
