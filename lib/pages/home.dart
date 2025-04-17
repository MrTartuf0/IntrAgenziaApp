import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:gap/gap.dart';
import 'package:intr_agenzia_app/io/dio_interceptor.dart';
import 'package:intr_agenzia_app/io/secure_storage_handler.dart';
import 'package:pretty_dio_logger/pretty_dio_logger.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final Dio dio = Dio();
  String _cookie = '';
  String _responseText = '';

  void fetchData() async {
    try {
      final response = await dio.get(
        'https://intragenzia.adisu.umbria.it/menu-odierni',
      );
      setState(() {
        _responseText =
            response.data.toString(); // or response.data['title'], etc.
      });
    } catch (e) {
      setState(() {
        _responseText = '❌ Error: $e';
      });
    }
  }

  @override
  void initState() {
    super.initState();

    dio.interceptors.addAll([
      PrettyDioLogger(requestHeader: true, responseHeader: true),
      CookieInterceptor(),
    ]);

    SecureStorageService().getCookie().then((cookie) {
      setState(() {
        _cookie = cookie ?? 'No cookie found';
      });
    });

    fetchData();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          child: Padding(
            padding: EdgeInsets.only(top: 24, left: 32, right: 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Buongiorno 🌤️ vit',
                  style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
                ),
                Gap(16),
                Text('🍪 $_cookie'),
                Gap(16),
                Text('📝 $_responseText'),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
