import 'package:dio/dio.dart';
import 'package:html/parser.dart' show parse;
import 'package:intr_agenzia_app/io/dio_interceptor.dart';

Future<Map<String, List<String>>> fetchPascoliMenus() async {
  final dio = Dio();
  dio.interceptors.add(CookieInterceptor());

  final urls = [
    'https://intragenzia.adisu.umbria.it/menu-odierni', // today
    'https://intragenzia.adisu.umbria.it/menu-domani', // tomorrow
  ];

  final nodeList = List.filled(4, '');
  final mensaList = List.filled(4, '');

  for (int i = 0; i < urls.length; i++) {
    try {
      final response = await dio.get(urls[i]);
      final document = parse(response.data);

      final anchors = document.querySelectorAll('div.view-menu a');

      // Track if lunch and dinner found
      bool lunchFound = false;
      bool dinnerFound = false;

      for (final anchor in anchors) {
        final text = anchor.text.trim();
        final href = anchor.attributes['href'] ?? '';

        if (text.contains('Mensa Pascoli')) {
          if (text.toLowerCase().contains('pranzo') && !lunchFound) {
            nodeList[i * 2] = href;
            mensaList[i * 2] = text;
            lunchFound = true;
          } else if (text.toLowerCase().contains('cena') && !dinnerFound) {
            nodeList[i * 2 + 1] = href;
            mensaList[i * 2 + 1] = text;
            dinnerFound = true;
          }
        }
      }
    } catch (e) {
      print('Error scraping ${urls[i]}: $e');
    }
  }

  return {'nodeList': nodeList, 'mensaList': mensaList};
}
