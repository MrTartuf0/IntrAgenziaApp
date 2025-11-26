import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:html/parser.dart';
import 'package:intr_agenzia_app/io/secure_storage_handler.dart';
import 'package:intr_agenzia_app/router.dart';
import 'package:top_snackbar_flutter/custom_snack_bar.dart';
import 'package:top_snackbar_flutter/top_snack_bar.dart';

class CookieInterceptor extends Interceptor {
  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    try {
      final cookie = await SecureStorageService().getCookie();
      if (cookie != null && cookie.isNotEmpty) {
        options.headers['Cookie'] = cookie;
      }
    } catch (e) {
      debugPrint('Failed to retrieve cookie: $e');
    }
    handler.next(options);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    final html = response.data.toString();

    if (isLoggedDom(html)) {
      print("User is logged in.");
      // You can do something here
    } else {
      print("User is not logged in.");
      // Handle unauthenticated state
    }

    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    // Empty for now
    handler.next(err);
  }

  bool isLoggedDom(String dom) {
    final document = parse(dom);
    final body = document.body;

    if (body == null) return false;

    final classes = body.classes;
    return classes.contains('user-logged-in');
  }

  static Future<void> login(
    String email,
    String password,
    BuildContext context,
  ) async {
    final Dio dio = Dio();
    try {
      final response = await dio.post(
        'https://intragenzia.adisu.umbria.it/user/login',
        options: Options(
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          followRedirects: false,
          validateStatus: (status) => true,
        ),
        data: {'name': email, 'pass': password, 'form_id': 'user_login_form'},
      );

      if (response.headers['set-cookie'] == null) {
        debugPrint("BRO MANCANO I BISCOTTI, vai a comprare le gocciole");
        showTopSnackBar(
          Overlay.of(context),
          CustomSnackBar.error(message: "Credenziali errate."),
        );
      } else {
        final cookie = response.headers['set-cookie']![0].split(';')[0];
        await SecureStorageService().saveCredentials(
          email: email,
          password: password,
          cookie: cookie,
        );

        appRouter.go('/home');
      }
    } catch (e) {
      showTopSnackBar(
        Overlay.of(context),
        CustomSnackBar.error(message: e.toString()),
      );
    }
  }
}
