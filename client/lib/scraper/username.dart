import 'package:dio/dio.dart';
import 'package:html/parser.dart' show parse;
import 'dart:convert';
import 'package:intr_agenzia_app/io/dio_interceptor.dart';

Future<String> fetchUserFullName() async {
  final dio = Dio();
  dio.interceptors.add(CookieInterceptor());

  try {
    final response = await dio.get(
      'https://intragenzia.adisu.umbria.it/dashboard',
    );
    final document = parse(response.data);

    // Find the specific <script> with the name in JSON
    final scriptTag = document.querySelector(
      'script[type="application/vnd.drupal-ajax"][data-big-pipe-replacement-for-placeholder-with-id*="italiagov_account_menu"]',
    );

    if (scriptTag == null) return '';

    // The content is a JSON array string
    final jsonData = json.decode(scriptTag.text) as List<dynamic>;

    // Extract the 'data' field (contains raw HTML)
    final htmlContent =
        jsonData.firstWhere(
          (element) =>
              element['command'] == 'insert' && element.containsKey('data'),
          orElse: () => {},
        )['data'] ??
        '';

    // Parse the injected HTML
    final injectedDoc = parse(htmlContent);
    final span = injectedDoc.querySelector('span.d-none.d-lg-block');

    return span?.text.trim() ?? '';
  } catch (e) {
    print('Error fetching user full name: $e');
    return '';
  }
}
