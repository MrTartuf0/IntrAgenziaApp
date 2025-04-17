import 'package:flutter/material.dart';
import 'package:intr_agenzia_app/io/secure_storage_handler.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String _cookie = '';

  @override
  void initState() {
    super.initState();
    SecureStorageService().getCookie().then((cookie) {
      setState(() {
        _cookie = cookie ?? 'No cookie found';
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(body: Center(child: Text('🍪 $_cookie')));
  }
}
