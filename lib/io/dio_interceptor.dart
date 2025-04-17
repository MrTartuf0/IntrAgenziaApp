import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intr_agenzia_app/io/secure_storage_handler.dart';
import 'package:top_snackbar_flutter/custom_snack_bar.dart';
import 'package:top_snackbar_flutter/top_snack_bar.dart';

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

Future<void> login(String email, String password, BuildContext context) async {
  final Dio _dio = Dio();
  try {
    final response = await _dio.post(
      'https://intragenzia.adisu.umbria.it/user/login',
      options: Options(
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        followRedirects: false,
        validateStatus: (status) => true,
      ),
      data: {'name': email, 'pass': password, 'form_id': 'user_login_form'},
    );

    if (response.headers['set-cookie'] == null) {
      print("BRO MANCANO I BISCOTTI, vai a comprare le gocciole");
      showTopSnackBar(
        Overlay.of(context),
        CustomSnackBar.error(message: "Credenziali errate."),
      );
    } else {
      final cookie = response.headers['set-cookie']![0].split(';')[0];
      SecureStorageService().saveCredentials(
        email: email,
        password: password,
        cookie: cookie,
      );

      context.go('/home');
    }
  } catch (e) {
    showTopSnackBar(
      Overlay.of(context),
      CustomSnackBar.error(message: e.toString()),
    );
  }
}
